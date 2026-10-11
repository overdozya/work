"""Explicit workflows; the model proposes, the application owns state and approval."""
import hashlib
from copy import deepcopy
from .fixtures import CASES, demo_map, demo_counterfactual, demo_scenario, demo_assessment
from .schemas import MAP, SCENARIO, COUNTERFACTUAL, ASSESSMENT, DIMENSIONS, Problem, dimensions, validate_map
from .store import now, uid

LABELS = {"observation": "단서 관찰", "context": "맥락 확인", "alternatives": "대안 비교", "reasoning": "근거 설명", "transfer": "새 상황 전이"}


def required_text(data, key, maximum=10000, minimum=1):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise Problem(f"{key}: {minimum}~{maximum}자 텍스트를 입력해 주세요.")
    return value.strip()


def revision(data, actual):
    if type(data.get("version")) is not int or data["version"] != actual:
        raise Problem("항목이 변경됐습니다. 새로고침 후 다시 시도해 주세요.", 409)


class Service:
    def __init__(self, store, provider=None, mode="demo", model="gemini-3.8-flash"):
        self.store, self.provider, self.mode, self.model = store, provider, mode, model

    def seed(self):
        existing = {x["id"] for x in self.store.list("cases")}
        for fixture in CASES:
            if fixture["id"] in existing:
                continue
            document = validate_map(demo_map(fixture), fixture["source"])
            self.store.save("cases", {"id": fixture["id"], "version": 1, "revision": 1,
                "created": now(), "domain": fixture["domain"], "source": fixture["source"], "original_source": fixture["source"],
                "interviews": [], "map": document, "status": "draft", "origin": "demo",
                "counterfactual": None, "approval": None}, event="seed")

    def generate(self, instruction, data, schema):
        if not self.provider:
            raise Problem("Gemini API 키가 설정되지 않았습니다. .env 설정 후 서버를 다시 실행해 주세요.", 503)
        return self.provider.generate(instruction, data, schema)

    def extract(self, data):
        if self.mode == "demo":
            raise Problem("데모는 준비된 세 사례를 체험합니다. 새 사례 추출은 .env에서 Gemini 모드를 설정해 주세요.", 503)
        source = required_text(data, "source", 16000, 80)
        domain = required_text(data, "domain", 100)
        result = self.generate("실제 작업 사례를 판단 지도로 추출하세요. 상황·단서·선택·근거·예외를 각각 포함하고 모두 연결하세요. 직접 관찰한 작업 기록이 아닌 회상은 expert_statement입니다. 원문에 없는 일반화는 ai_inference, quote는 빈 문자열입니다. 인용은 원문에서 연속된 부분을 정확히 복사하세요. knowledge와 questions의 id는 각각 중복 없이 작성하세요. 불확실한 부분을 확인하는 인터뷰 질문 2~4개와 다섯 차원별 rubric을 제안하세요.", {"domain": domain, "source": source}, MAP)
        validate_map(result, source)
        return self.store.save("cases", {"id": uid(), "version": 1, "revision": 1, "created": now(),
            "domain": domain, "source": source, "original_source": source, "interviews": [], "map": result,
            "status": "draft", "origin": "gemini", "counterfactual": None, "approval": None}, event="extraction")

    def interview(self, key, data):
        case = self.store.get("cases", key)
        revision(data, case["version"])
        if self.mode == "demo":
            raise Problem("추가 인터뷰와 재추출은 Gemini 모드에서 가능합니다.", 503)
        qid = required_text(data, "question_id", 60)
        question = next((q for q in case["map"]["questions"] if q["id"] == qid), None)
        if not question:
            raise Problem("현재 지도에 없는 질문입니다.")
        answer = required_text(data, "answer", 3000, 10)
        source = case["source"] + f"\n\n추가 인터뷰\n질문: {question['question']}\n전문가 답변: {answer}"
        if len(source) > 24000:
            raise Problem("인터뷰가 길어졌습니다. 별도 사례로 나눠 주세요.")
        document = self.generate("추가 인터뷰를 반영해 판단 지도를 다시 작성하세요. 검증되지 않은 일반화는 AI 해석으로 남기세요. 인용은 source의 정확한 부분 문자열이어야 합니다. 모든 다섯 노드 종류와 평가 차원을 포함하세요. 해소되지 않은 쟁점을 후속 질문으로 남기세요.", {"source": source, "previous_map": case["map"]}, MAP)
        validate_map(document, source)
        expected = case["version"]
        case.update(source=source, map=document, revision=case["revision"] + 1, version=expected + 1,
                    counterfactual=None, approval=None, status="draft", origin="gemini")
        case["interviews"].append({"question": question["question"], "answer": answer, "created": now()})
        return self.store.save("cases", case, expected, "interview_revised")

    def counterfactual(self, key, data):
        case = self.store.get("cases", key)
        revision(data, case["version"])
        change = required_text(data, "change", 1000, 5)
        if self.mode == "demo":
            fixture = next((x for x in CASES if x["id"] == key), None)
            if not fixture:
                raise Problem("실제 사례의 반례는 Gemini 모드에서만 생성합니다.", 503)
            result = demo_counterfactual(fixture, change)
        else:
            result = self.generate("지정된 조건 하나를 바꾸어 기존 판단 규칙의 경계를 시험하세요. 기존 규칙이 살아남는지, 선택이 어떻게 달라지는지와 이유를 구체적으로 제시하세요. 전문가가 답할 검증 질문을 포함하세요. 확실하지 않으면 왜 추가 검증이 필요한지 밝히세요.", {"map": case["map"], "source": case["source"], "change": change}, COUNTERFACTUAL)
        expected = case["version"]
        case.update(version=expected + 1, status="draft", approval=None,
                    counterfactual={"result": result, "origin": self.mode, "review": None})
        return self.store.save("cases", case, expected, "counterfactual_proposed")

    def review(self, key, data):
        case = self.store.get("cases", key)
        revision(data, case["version"])
        if not case["counterfactual"]:
            raise Problem("먼저 조건을 바꾸어 반례를 생성해 주세요.", 409)
        verdict = data.get("verdict")
        if verdict not in ("confirmed", "revise"):
            raise Problem("검토 결과를 선택해 주세요.")
        note = required_text(data, "note", 2000, 10)
        reviewer = required_text(data, "reviewer", 100)
        expected = case["version"]
        case["counterfactual"]["review"] = {"verdict": verdict, "note": note, "reviewer": reviewer, "created": now()}
        case.update(version=expected + 1, status="reviewed" if verdict == "confirmed" else "draft", approval=None)
        return self.store.save("cases", case, expected, "expert_review")

    def approve(self, key, data):
        case = self.store.get("cases", key)
        revision(data, case["version"])
        review = (case.get("counterfactual") or {}).get("review")
        if not review or review["verdict"] != "confirmed":
            raise Problem("반례를 검토하고 적용 경계를 확인한 뒤 승인할 수 있습니다.", 409)
        if data.get("confirmed") is not True:
            raise Problem("원문·해석·적용 경계를 직접 확인했다는 체크가 필요합니다.")
        expected = case["version"]
        case.update(version=expected + 1, status="approved",
                    approval={"id": uid(), "reviewer": review["reviewer"], "note": review["note"], "revision": case["revision"], "created": now()})
        return self.store.save("cases", case, expected, "knowledge_approved")

    def plan(self, key):
        case = self.store.get("cases", key)
        sessions = [s for s in self.store.list("sessions") if s["case_id"] == key and s["case_revision"] == case["revision"] and s.get("assessment") and s["origin"] == "gemini"]
        level = 0
        scores = {d: [] for d in DIMENSIONS}
        consecutive = []
        seen = set()
        for session in sessions:
            for item in session["assessment"]["dimensions"]:
                scores[item["dimension"]].append(item["score"])
            signature = session["signature"]
            strong = session["hints_used"] == 0 and min(x["score"] for x in session["assessment"]["dimensions"]) >= 3
            if strong and signature not in seen:
                consecutive.append(signature)
                seen.add(signature)
                if len(consecutive) >= 2:
                    level = min(3, level + 1)
                    consecutive = []
            else:
                consecutive = []
        averages = {d: round(sum(v[-5:]) / len(v[-5:]), 2) if v else None for d, v in scores.items()}
        focus = min(DIMENSIONS, key=lambda d: averages[d] if averages[d] is not None else -1)
        return {"level": level, "focus": focus, "averages": averages,
                "attempts": len(sessions), "evidence_needed": max(0, 2 - len(consecutive))}

    def start(self, data):
        key = required_text(data, "case_id", 60)
        case = self.store.get("cases", key)
        if case["status"] != "approved":
            raise Problem("먼저 전문가 검토와 지식 승인을 완료해 주세요.", 409)
        if self.mode == "demo" and case["origin"] != "demo":
            raise Problem("실제 사례 훈련은 Gemini 모드에서만 가능합니다.", 503)
        # Reuse an unfinished trial; repeated clicks never purchase a second scenario.
        for active in reversed(self.store.list("sessions")):
            if active["case_id"] == key and active["case_revision"] == case["revision"] and active.get("case_approval") == case["approval"]["id"] and active["origin"] == self.mode and not active.get("assessment"):
                return self.public_session(active)
        plan = self.plan(key)
        if self.mode == "demo":
            fixture = next(x for x in CASES if x["id"] == key)
            scenario = demo_scenario(fixture, plan["level"], plan["focus"])
        else:
            previous = [s["scenario"]["brief"] for s in self.store.list("sessions") if s["case_id"] == key][-8:]
            scenario = self.generate("승인된 지도를 바탕으로 새로운 전이 훈련 문제를 만드세요. 원래 사례와 다른 소재·목적·관람 조건으로 바꾸되 배운 원칙을 적용하거나 경계를 판단할 수 있게 하세요. 기존 문제를 반복하지 마세요. brief와 task에 정답을 노출하지 마세요. options는 타당할 수 있는 대안 3~4개, hints는 점점 구체적인 3개입니다. expert_notes와 criteria는 서버 평가용입니다. 다섯 평가 차원을 중복 없이 포함하세요. 한 대안만 유일한 정답이라고 단정하지 마세요.", {"map": case["map"], "review": case["approval"], "plan": plan, "previous_scenarios": previous}, SCENARIO)
        dimensions(scenario["criteria"])
        options = [o["id"] for o in scenario["options"]]
        if len(set(options)) != len(options) or any(not x for x in options):
            raise Problem("훈련 선택지 식별자가 유효하지 않습니다.", 502)
        signature = hashlib.sha256(scenario["brief"].encode()).hexdigest()
        if self.mode == "gemini" and any(s["case_id"] == key and s["signature"] == signature for s in self.store.list("sessions")):
            raise Problem("이전과 동일한 문제가 생성되었습니다. 새 문제를 다시 요청해 주세요.", 502)
        session = {"id": uid(), "version": 1, "created": now(), "case_id": key, "case_revision": case["revision"], "case_approval": case["approval"]["id"],
                   "map_snapshot": deepcopy(case["map"]), "scenario": scenario, "signature": signature,
                   "level": plan["level"], "focus": plan["focus"], "hint_budget": [3, 2, 0, 0][plan["level"]],
                   "hints_used": 0, "answer": None, "assessment": None, "origin": self.mode}
        self.store.save("sessions", session, event="training_started")
        return self.public_session(session)

    def current_case(self, session):
        case = self.store.get("cases", session["case_id"])
        if case["status"] != "approved" or case["revision"] != session["case_revision"] or case["approval"]["id"] != session.get("case_approval"):
            raise Problem("사례가 수정되었거나 승인이 해제되었습니다. 재검토 후 새 훈련을 시작해 주세요.", 409)
        return case

    def hint(self, key, data):
        session = self.store.get("sessions", key)
        revision(data, session["version"])
        self.current_case(session)
        if session["assessment"] or session["hints_used"] >= session["hint_budget"]:
            raise Problem("이번 훈련에서 사용할 수 있는 힌트가 없습니다.", 409)
        expected = session["version"]
        session.update(version=expected + 1, hints_used=session["hints_used"] + 1)
        self.store.save("sessions", session, expected, "hint_used")
        return self.public_session(session)

    def assess(self, key, data):
        session = self.store.get("sessions", key)
        revision(data, session["version"])
        self.current_case(session)
        if session["assessment"]:
            raise Problem("이미 제출한 훈련입니다. 새 문제를 시작해 주세요.", 409)
        answer = required_text(data, "reasoning", 4000, 20)
        option = required_text(data, "option_id", 60)
        selected = next((o for o in session["scenario"]["options"] if o["id"] == option), None)
        if not selected:
            raise Problem("제시된 선택지 중 하나를 선택해 주세요.")
        confidence = data.get("confidence")
        if type(confidence) is not int or not 0 <= confidence <= 100:
            raise Problem("확신도는 0~100 사이 정수여야 합니다.")
        if self.mode != session["origin"]:
            raise Problem("서버 모드가 변경됐습니다. 새 훈련을 시작해 주세요.", 409)
        submission = {"reasoning": answer, "option": selected, "confidence": confidence}
        if self.mode == "demo":
            assessment = demo_assessment()
        else:
            assessment = self.generate("학습자의 실제 답안만 근거로 다섯 차원을 0~4점 평가하세요(0=근거 없음,1=언급,2=부분 적용,3=맥락에 타당한 적용,4=예외까지 독립 설명). evidence에는 답안의 정확한 인용을 넣고, 근거가 없으면 빈 문자열로 쓰세요. 사전 criteria와 비교하세요. 전문가와 선택이 달라도 근거가 타당하면 인정하세요. confidence 자체나 답변 길이에 점수를 주지 마세요. 힌트로 이미 제공된 내용을 독립 능력으로 과장하지 마세요. 구체적인 다음 연습을 제안하세요.", {"scenario": session["scenario"], "map": session["map_snapshot"], "submission": submission, "hints_used": session["hints_used"]}, ASSESSMENT)
            dimensions(assessment["dimensions"])
            for item in assessment["dimensions"]:
                if item["evidence"] and item["evidence"] not in answer:
                    raise Problem("피드백의 근거 인용이 답안에서 확인되지 않습니다. 다시 평가해 주세요.", 502)
                if item["score"] > 0 and not item["evidence"].strip():
                    raise Problem("평가 점수에 답안 근거가 없습니다. 다시 평가해 주세요.", 502)
        self.current_case(session)
        expected = session["version"]
        session.update(version=expected + 1, answer=submission, assessment=assessment, submitted=now())
        self.store.save("sessions", session, expected, "training_assessed")
        return self.public_session(session)

    @staticmethod
    def public_session(session):
        public = deepcopy(session)
        public.pop("map_snapshot", None)
        public["scenario"].pop("expert_notes", None)
        public["scenario"].pop("criteria", None)
        public["scenario"]["hints"] = session["scenario"]["hints"][:session["hints_used"]]
        return public

    def progress(self):
        cases = self.store.list("cases")
        sessions = self.store.list("sessions")
        return {"plans": {c["id"]: self.plan(c["id"]) for c in cases},
                "sessions": [self.public_session(s) for s in sessions], "labels": LABELS}

    def export(self):
        return {"format": "judgment-atelier/v1", "exported": now(), "mode": self.mode,
                "cases": self.store.list("cases"), "sessions": self.store.list("sessions"),
                "events": self.store.list("events"), "notice": "단일 사용자의 탐색 기록입니다. 교육 효과나 객관적 숙련도를 입증하는 연구 결과가 아닙니다."}
