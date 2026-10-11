"""SQLite is runtime data, stored only under .local. Revision compare-and-swap."""
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .schemas import Problem


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, created TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            with db:
                db.execute("PRAGMA journal_mode=WAL")
                yield db

    def list(self, table):
        assert table in ("cases", "sessions", "events")
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(f"SELECT data FROM {table} ORDER BY rowid")]

    def get(self, table, key):
        assert table in ("cases", "sessions")
        with self.connection() as db:
            row = db.execute(f"SELECT data FROM {table} WHERE id=?", (key,)).fetchone()
        if not row:
            raise Problem("찾을 수 없는 사례 또는 훈련입니다.", 404)
        return json.loads(row[0])

    def save(self, table, data, expected=None, event=None):
        assert table in ("cases", "sessions")
        with self.connection() as db:
            if expected is None:
                try:
                    db.execute(f"INSERT INTO {table} VALUES(?,?,?)", (data["id"], data["version"], json.dumps(data, ensure_ascii=False)))
                except sqlite3.IntegrityError:
                    raise Problem("이미 존재하는 항목입니다.", 409) from None
            else:
                result = db.execute(f"UPDATE {table} SET version=?, data=? WHERE id=? AND version=?",
                    (data["version"], json.dumps(data, ensure_ascii=False), data["id"], expected))
                if result.rowcount != 1:
                    raise Problem("다른 작업에서 항목이 변경됐습니다. 새로고침 후 다시 시도해 주세요.", 409)
            if event:
                entry = {"id": uid(), "created": now(), "kind": event, "subject": data["id"], "version": data["version"]}
                db.execute("INSERT INTO events VALUES(?,?,?,?)", (entry["id"], entry["created"], event, json.dumps(entry)))
        return data
