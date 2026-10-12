from agent_eval.tools.schema import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "count": {"type": "integer", "minimum": 0},
        "status": {"type": "string", "enum": ["open", "closed"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["path"],
    "additionalProperties": False,
}


def test_valid_arguments_produce_no_problems():
    assert validate({"path": "/a", "count": 2, "status": "open", "tags": ["x"]}, SCHEMA) == []


def test_missing_required_key():
    assert validate({}, SCHEMA) == ["$: missing required key 'path'"]


def test_wrong_type_and_bool_is_not_integer():
    assert validate({"path": 3}, SCHEMA) == ["$.path: expected string, got int"]
    assert validate({"path": "/a", "count": True}, SCHEMA) == [
        "$.count: expected integer, got bool"
    ]


def test_unknown_key_rejected():
    assert "$: unknown key 'file'" in validate({"path": "/a", "file": "/b"}, SCHEMA)


def test_enum_minimum_and_items():
    problems = validate({"path": "/a", "status": "done", "count": -1, "tags": [1]}, SCHEMA)
    assert "$.status: 'done' is not one of ['open', 'closed']" in problems
    assert "$.count: -1 is below minimum 0" in problems
    assert "$.tags[0]: expected string, got int" in problems


def test_non_object_top_level_reports_type_only():
    assert validate("nope", SCHEMA) == ["$: expected object, got str"]
