"""Loopback-only local app, no third-party runtime dependencies."""
import json
import logging
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .gemini import Gemini
from .schemas import Problem
from .service import Service
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MAX_BODY = 128 * 1024


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in {"GEMINI_API_KEY", "GEMINI_MODEL", "ATELIER_MODE", "ATELIER_PORT"}:
            os.environ.setdefault(name, value.strip().strip('"\''))


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service):
        self.service = service
        self.csrf = secrets.token_urlsafe(32)
        self.gate = threading.BoundedSemaphore(1)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "JudgmentAtelier/0.1"

    def log_message(self, format, *args):
        # No sources, prompts, API keys, request bodies or query strings in logs.
        return

    def send(self, status, payload, content_type="application/json; charset=utf-8"):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False).encode()
        if isinstance(payload, str):
            payload = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(payload)

    def guard(self, mutate=False):
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            raise Problem("허용하지 않는 Host입니다.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in allowed}:
            raise Problem("다른 사이트에서 요청할 수 없습니다.", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise Problem("다른 사이트에서 요청할 수 없습니다.", 403)
        if mutate and not secrets.compare_digest(self.headers.get("X-Atelier-Token", ""), self.server.csrf):
            raise Problem("보안 토큰이 만료됐습니다. 페이지를 새로고침해 주세요.", 403)

    def do_GET(self):
        try:
            self.guard()
            route = urlsplit(self.path).path
            service = self.server.service
            if route == "/api/status":
                self.send(200, {"ok": True, "mode": service.mode, "model": service.model,
                    "configured": service.provider is not None, "csrf": self.server.csrf,
                    "notice": "Gemini 모드에서는 입력한 사례·인터뷰·답안이 Google API로 전송됩니다."})
            elif route == "/api/cases":
                self.send(200, service.store.list("cases"))
            elif route.startswith("/api/cases/"):
                self.send(200, service.store.get("cases", route.split("/")[-1]))
            elif route.startswith("/api/sessions/"):
                self.send(200, service.public_session(service.store.get("sessions", route.split("/")[-1])))
            elif route == "/api/progress":
                self.send(200, service.progress())
            elif route == "/api/export":
                self.send(200, service.export())
            else:
                files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
                if route not in files:
                    raise Problem("찾을 수 없는 페이지입니다.", 404)
                filename, kind = files[route]
                self.send(200, (WEB / filename).read_bytes(), kind)
        except Problem as error:
            self.send(error.status, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            logging.exception("local GET failed")
            self.send(500, {"error": "로컬 서버 오류입니다. 다시 시도해 주세요."})

    def do_POST(self):
        acquired = False
        try:
            self.guard(mutate=True)
            if self.headers.get("Transfer-Encoding"):
                raise Problem("전송 인코딩을 지원하지 않습니다.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise Problem("본문 크기가 올바르지 않습니다.") from None
            if not 0 < length <= MAX_BODY:
                raise Problem("입력 크기가 허용 범위를 벗어났습니다.", 413)
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise Problem("JSON 입력이 필요합니다.", 415)
            self.connection.settimeout(10)
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, TimeoutError):
                raise Problem("JSON 입력을 읽을 수 없습니다.") from None
            if not isinstance(data, dict):
                raise Problem("JSON 객체를 입력해 주세요.")
            acquired = self.server.gate.acquire(blocking=False)
            if not acquired:
                raise Problem("다른 작업을 처리하고 있습니다. 완료 후 다시 시도해 주세요.", 429)
            parts = urlsplit(self.path).path.strip("/").split("/")
            service = self.server.service
            if parts == ["api", "cases"]:
                result = service.extract(data)
            elif parts == ["api", "sessions"]:
                result = service.start(data)
            elif len(parts) == 4 and parts[:2] == ["api", "cases"]:
                actions = {"interview": service.interview, "counterfactual": service.counterfactual, "review": service.review, "approve": service.approve}
                if parts[3] not in actions:
                    raise Problem("찾을 수 없는 작업입니다.", 404)
                result = actions[parts[3]](parts[2], data)
            elif len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] in ("hint", "assess"):
                result = (service.hint if parts[3] == "hint" else service.assess)(parts[2], data)
            else:
                raise Problem("찾을 수 없는 작업입니다.", 404)
            self.send(200, result)
        except Problem as error:
            self.send(error.status, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            logging.exception("local POST failed")
            self.send(500, {"error": "로컬 서버 오류입니다. 다시 시도해 주세요."})
        finally:
            if acquired:
                self.server.gate.release()


def main():
    load_env(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "")
    mode = os.environ.get("ATELIER_MODE", "gemini" if key else "demo")
    if mode not in ("gemini", "demo"):
        raise SystemExit("ATELIER_MODE는 gemini 또는 demo여야 합니다.")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    provider = Gemini(key, model) if mode == "gemini" and key else None
    service = Service(Store(ROOT / ".local" / "atelier.sqlite3"), provider, mode, model)
    service.seed()
    port = int(os.environ.get("ATELIER_PORT", "8791"))
    with Server(("127.0.0.1", port), service) as server:
        print(f"판단 공방 · {mode} · http://127.0.0.1:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
