"""Authored demonstration cases. These are never presented as Gemini generations."""
from copy import deepcopy
from .schemas import DIMENSIONS

CASES = [
    {
        "id": "demo-space", "title": "여백이 많으면, 늘 좋은 걸까?", "domain": "편집 디자인",
        "source": "전시 포스터를 만들던 때의 사례입니다. A2 크기로 출력하고 3m 떨어져서 봤어요. 목적은 정보를 빠르게 전달하기보다 두 인물 사이의 긴장감을 보여주는 것이었어요. 초안에서는 두 인물 사이의 여백이 커서 시선이 각자 흩어졌습니다. 저는 두 인물 사이의 간격을 줄이고 제목을 그 사이에 놓았어요. 시선이 두 인물과 제목 사이를 오가게 하려는 선택이었죠. 다만 같은 구성을 행사 안내문에 쓰진 않아요. 날짜와 장소를 빨리 읽어야 한다면 정보 영역의 여백을 충분히 확보합니다.",
        "concept": "여백과 시각적 위계", "cue": "두 인물 사이로 흩어지는 시선", "decision": "간격을 줄여 시선의 긴장감을 만든다",
        "quotes": ["목적은 정보를 빠르게 전달하기보다 두 인물 사이의 긴장감을 보여주는 것이었어요.", "초안에서는 두 인물 사이의 여백이 커서 시선이 각자 흩어졌습니다.", "저는 두 인물 사이의 간격을 줄이고 제목을 그 사이에 놓았어요.", "시선이 두 인물과 제목 사이를 오가게 하려는 선택이었죠.", "날짜와 장소를 빨리 읽어야 한다면 정보 영역의 여백을 충분히 확보합니다."],
        "exception": "날짜·장소를 빨리 읽어야 하는 안내물", "when": "전시 포스터에서 인물 사이의 긴장감을 만들고 싶고 시선이 흩어질 때",
        "because": "요소 사이의 관계를 가까이 묶어 시선이 왕복하도록 하기 위해",
    },
    {
        "id": "demo-color", "title": "강한 색이 주인공을 가릴 때", "domain": "시각 디자인",
        "source": "사진이 중심인 전시 리플릿을 작업했어요. 사진 속 붉은 꽃을 먼저 보게 하는 것이 목적이었습니다. 배경까지 채도가 높아서 꽃과 배경이 동시에 눈에 들어왔어요. 저는 배경의 채도를 낮추고 사진의 붉은색은 유지했습니다. 대비를 더하는 대신 경쟁하는 요소를 덜어낸 거죠. 하지만 축제의 에너지를 표현하는 포스터라면 배경과 사진의 강한 색이 함께 살아 있어도 좋습니다. 인쇄에서는 종이와 조명에 따라 색이 달라지니 교정지를 꼭 확인해요.",
        "concept": "채도와 주의 경쟁", "cue": "꽃과 배경이 동시에 눈에 들어온다", "decision": "주인공 대신 배경의 채도를 낮춘다",
        "quotes": ["사진 속 붉은 꽃을 먼저 보게 하는 것이 목적이었습니다.", "배경까지 채도가 높아서 꽃과 배경이 동시에 눈에 들어왔어요.", "저는 배경의 채도를 낮추고 사진의 붉은색은 유지했습니다.", "대비를 더하는 대신 경쟁하는 요소를 덜어낸 거죠.", "축제의 에너지를 표현하는 포스터라면 배경과 사진의 강한 색이 함께 살아 있어도 좋습니다."],
        "exception": "복수의 강한 색으로 축제 에너지를 표현할 때", "when": "사진의 특정 요소가 주인공인데 배경의 색이 시선을 뺏을 때",
        "because": "강조 대상을 더 자극하기보다 주의를 경쟁하는 배경을 줄이기 위해",
    },
    {
        "id": "demo-type", "title": "제목을 키우기 전에 볼 것", "domain": "타이포그래피",
        "source": "작은 독립 서점의 행사 카드뉴스를 만들었어요. 휴대폰 화면에서 행사 제목이 먼저 읽혀야 했습니다. 그런데 제목보다 여러 개의 굵은 부제에 먼저 눈이 갔어요. 제목을 더 키우는 방법도 고려했지만 이미 화면을 많이 차지하고 있었어요. 그래서 부제의 굵기를 낮추고 부제끼리 묶었습니다. 크기를 더하지 않고 주변의 위계를 낮춰 제목을 먼저 읽게 했죠. 단, 고령자가 멀리서 보는 게시물이라면 실제 글자 크기와 명도 대비를 먼저 확보해야 합니다.",
        "concept": "크기와 상대적 위계", "cue": "제목보다 굵은 부제가 먼저 읽힌다", "decision": "부제의 굵기를 낮추고 그룹으로 묶는다",
        "quotes": ["휴대폰 화면에서 행사 제목이 먼저 읽혀야 했습니다.", "그런데 제목보다 여러 개의 굵은 부제에 먼저 눈이 갔어요.", "그래서 부제의 굵기를 낮추고 부제끼리 묶었습니다.", "크기를 더하지 않고 주변의 위계를 낮춰 제목을 먼저 읽게 했죠.", "고령자가 멀리서 보는 게시물이라면 실제 글자 크기와 명도 대비를 먼저 확보해야 합니다."],
        "exception": "고령자가 멀리서 읽는 게시물의 글자 크기·대비가 부족할 때", "when": "제목의 크기가 충분하지만 굵은 부제들이 시선을 경쟁할 때",
        "because": "위계는 절대적인 크기만이 아니라 주변 요소와의 관계로 결정되기 때문에",
    },
]

CRITERIA = {
    "observation": "실제 시선이 경쟁하거나 읽기 어려운 위치를 구체적으로 짚는다.",
    "context": "목적·매체·관람 거리 중 판단을 바꾸는 조건을 확인한다.",
    "alternatives": "두 가지 이상의 가능한 조치를 비교한다.",
    "reasoning": "조치와 관찰 단서 사이의 인과를 설명한다.",
    "transfer": "기존 사례와 다른 조건을 발견하고 예외 또는 추가 확인을 제안한다.",
}


def demo_map(case):
    labels = [case["when"], case["cue"], case["decision"], case["because"], case["exception"]]
    kinds = ["context", "cue", "choice", "reason", "exception"]
    nodes = [{"id": kind, "kind": kind, "label": label, "detail": quote,
              "evidence": {"quote": quote, "provenance": "expert_statement"}}
             for kind, label, quote in zip(kinds, labels, case["quotes"])]
    return {
        "title": case["title"], "summary": "결론보다, 그 결론이 유효해지는 조건을 살펴보는 디자인 판단 사례.",
        "knowledge": [{"id": "visual-hierarchy", "label": case["concept"], "description": "요소를 따로 보기보다 목적과 주변 관계를 함께 읽는 기초 지식."},
                      {"id": "purpose", "label": "목적과 매체", "description": "같은 구성이라도 목적·매체·관람 거리가 달라지면 판단이 달라진다."}],
        "nodes": nodes,
        "edges": [{"source": "context", "target": "cue", "relation": "어디를 관찰할지 정한다"},
                  {"source": "cue", "target": "choice", "relation": "선택을 이끈다"},
                  {"source": "reason", "target": "choice", "relation": "선택을 정당화한다"},
                  {"source": "exception", "target": "context", "relation": "적용 범위를 제한한다"}],
        "rule": {"when": case["when"], "then": case["decision"], "because": case["because"], "exceptions": [case["exception"]]},
        "questions": [{"id": "q1", "question": "다른 수정안도 시도했나요? 그 안을 버린 단서는 무엇이었나요?", "purpose": "회상 속 결론과 실제 대안 비교를 구분합니다."},
                      {"id": "q2", "question": "판단이 달라질 만한 목적이나 관람 조건은 무엇인가요?", "purpose": "일반화할 수 있는 범위를 확인합니다."}],
        "rubric": [{"dimension": d, "criterion": CRITERIA[d]} for d in DIMENSIONS],
    }


def demo_counterfactual(case, change):
    return {"changed_condition": change, "scenario": f"같은 작업에서 조건을 바꿉니다: {change}. 원래 사례의 목적·관람 환경과 같은지부터 확인해야 합니다.",
            "changed_decision": f"원래 선택인 ‘{case['decision']}’을 곧바로 적용하지 않고, {case['exception']}에 해당하는지 먼저 확인합니다.",
            "why": "이 결과는 고정 데모입니다. 입력 조건을 의미적으로 분석하지 않습니다. 실제 판단 변화는 Gemini 모드에서 생성됩니다.",
            "question": "바뀐 조건에서도 이 선택이 타당한가요? 실제 경험으로 적용 범위를 확인해 주세요.",
            "rule_survives": False, "boundary": case["exception"]}


def demo_scenario(case, level, focus):
    return {
        "title": "전시 포스터가 동네 안내문이 된다면",
        "brief": "동네 주민을 위한 야간 전시 안내물입니다. A4 크기로 출력해 입구에 붙이고, 2m 밖에서 날짜와 장소를 읽습니다. 시안을 보니 강한 제목과 두 이미지 사이에 날짜가 끼어 있고, 모든 글자가 굵습니다. 전시의 긴장감보다 방문 정보를 빠르게 찾는 일이 우선입니다.",
        "task": "먼저 확인할 단서, 가능한 대안, 선택할 조치와 그 이유를 설명해 주세요. 조건을 더 확인해도 좋습니다.",
        "options": [{"id": "a", "label": "원래 사례의 수정 방법을 그대로 적용한다"},
                    {"id": "b", "label": "날짜·장소의 읽힘을 확인하고 정보 영역을 따로 묶는다"},
                    {"id": "c", "label": "모든 요소의 크기와 대비를 함께 높인다"}],
        "hints": ["이 작업에서 관객이 가장 먼저 해야 할 행동은 무엇일까요?", "2m 밖에서 날짜를 실제로 읽어 보세요. 제목을 더 키우는 방법과 정보 영역을 분리하는 방법을 비교해 보세요.", "원래 사례의 표현 목적과 현재의 정보 전달 목적이 다릅니다. 정보 영역의 가독성을 확보하는 선택을 자신의 관찰로 정당화해 보세요."],
        "changed_condition": "표현 중심 포스터 → 방문 정보를 전달하는 안내물",
        "expert_notes": "날짜·장소의 가독성과 관람 거리를 확인한다. 정보 그룹 분리, 굵기 차등, 여백 확보 등의 대안을 비교한다. 다른 선택도 조건과 근거가 타당하면 인정한다.",
        "criteria": [{"dimension": d, "criterion": CRITERIA[d]} for d in DIMENSIONS],
    }


def demo_assessment():
    return {"feedback": "데모에서는 답안의 질을 자동 채점하지 않습니다. 아래 기준으로 자신의 설명을 점검해 보세요. Gemini 모드에서는 답안의 근거를 인용해 항목별 피드백을 제공합니다.",
            "dimensions": [{"dimension": d, "score": 0, "evidence": "데모 모드: 수행 평가 없음", "next_practice": CRITERIA[d]} for d in DIMENSIONS],
            "missed_cues": [], "strong_points": []}
