"""Small JSON-schema subset shared by Gemini and the local validation boundary."""
import math


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(maximum=2000, minimum=1):
    return {"type": "string", "minLength": minimum, "maxLength": maximum}


def enum(*values):
    return {"type": "string", "enum": list(values)}


def array(item, minimum=0, maximum=20):
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


DIMENSIONS = ("observation", "context", "alternatives", "reasoning", "transfer")
EVIDENCE = obj(quote=text(3000, 0), provenance=enum("observation", "expert_statement", "ai_inference"))
MAP = obj(
    title=text(100), summary=text(500),
    knowledge=array(obj(id=text(60), label=text(100), description=text(500)), 1, 8),
    nodes=array(obj(id=text(60), kind=enum("context", "cue", "choice", "reason", "exception"),
                    label=text(100), detail=text(1000), evidence=EVIDENCE), 5, 12),
    edges=array(obj(source=text(60), target=text(60), relation=text(100)), 4, 20),
    rule=obj(when=text(500), then=text(500), because=text(500), exceptions=array(text(500), 1, 5)),
    questions=array(obj(id=text(60), question=text(300), purpose=text(300)), 2, 4),
    rubric=array(obj(dimension=enum(*DIMENSIONS), criterion=text(500)), 5, 5),
)
COUNTERFACTUAL = obj(changed_condition=text(500), scenario=text(1500), changed_decision=text(500),
                     why=text(1000), question=text(500), rule_survives={"type": "boolean"}, boundary=text(1000))
SCENARIO = obj(title=text(150), brief=text(2000), task=text(500),
               options=array(obj(id=text(60), label=text(500)), 3, 4),
               hints=array(text(500), 3, 3), changed_condition=text(500),
               expert_notes=text(2000), criteria=array(obj(dimension=enum(*DIMENSIONS), criterion=text(500)), 5, 5))
SCORE = {"type": "integer", "minimum": 0, "maximum": 4}
ASSESSMENT = obj(
    feedback=text(2000), dimensions=array(obj(dimension=enum(*DIMENSIONS), score=SCORE,
        evidence=text(500, 0), next_practice=text(500)), 5, 5),
    missed_cues=array(text(500), 0, 8), strong_points=array(text(500), 0, 8),
)


def validate(value, schema, path="응답"):
    kind = schema["type"]
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": type(value) is bool,
             "integer": type(value) is int, "number": type(value) in (int, float)}[kind]
    if not valid:
        raise Problem(f"{path}: {kind} 형식이 필요합니다.", 502)
    if kind == "object":
        if set(value) - set(schema["properties"]) or set(schema["required"]) - set(value):
            raise Problem(f"{path}: 필드가 누락되거나 허용하지 않은 필드가 있습니다.", 502)
        for key, sub in schema["properties"].items():
            validate(value[key], sub, f"{path}.{key}")
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100):
            raise Problem(f"{path}: 항목 수가 범위를 벗어났습니다.", 502)
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value.strip()) <= schema.get("maxLength", 10000):
            raise Problem(f"{path}: 텍스트 길이가 허용 범위를 벗어났습니다.", 502)
        if "enum" in schema and value not in schema["enum"]:
            raise Problem(f"{path}: 허용하지 않은 값입니다.", 502)
    elif kind in ("integer", "number"):
        if not math.isfinite(value) or not schema.get("minimum", -1e9) <= value <= schema.get("maximum", 1e9):
            raise Problem(f"{path}: 숫자가 범위를 벗어났습니다.", 502)
    return value


def dimensions(items):
    if len(items) != 5 or {x["dimension"] for x in items} != set(DIMENSIONS):
        raise Problem("평가 기준은 다섯 판단 능력을 중복 없이 포함해야 합니다.", 502)


def validate_map(data, source):
    validate(data, MAP)
    ids = [n["id"] for n in data["nodes"]]
    if any(not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise Problem("판단 지도에 비어 있거나 중복된 노드가 있습니다.", 502)
    if {n["kind"] for n in data["nodes"]} != {"context", "cue", "choice", "reason", "exception"}:
        raise Problem("판단 지도에는 상황·단서·선택·근거·예외가 모두 필요합니다.", 502)
    for collection in (data["knowledge"], data["questions"]):
        keys = [x["id"] for x in collection]
        if any(not k.strip() for k in keys) or len(keys) != len(set(keys)):
            raise Problem("지식 또는 질문 식별자가 중복되었습니다.", 502)
    connections = {i: set() for i in ids}
    for edge in data["edges"]:
        if edge["source"] not in ids or edge["target"] not in ids or edge["source"] == edge["target"]:
            raise Problem("판단 지도의 연결이 유효하지 않습니다.", 502)
        connections[edge["source"]].add(edge["target"])
        connections[edge["target"]].add(edge["source"])
    visited, pending = set(), [ids[0]]
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(connections[node] - visited)
    if visited != set(ids):
        raise Problem("판단 지도의 노드가 서로 연결되지 않았습니다.", 502)
    for node in data["nodes"]:
        e = node["evidence"]
        if e["provenance"] != "ai_inference" and (not e["quote"].strip() or e["quote"] not in source):
            raise Problem("원문에서 확인할 수 없는 인용이 있습니다. 다시 추출해 주세요.", 502)
        if e["provenance"] == "ai_inference" and e["quote"]:
            raise Problem("AI 해석을 원문 인용으로 표시할 수 없습니다.", 502)
    dimensions(data["rubric"])
    return data
