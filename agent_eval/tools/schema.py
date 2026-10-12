"""Minimal JSON-schema validation for tool arguments.

Covers what tool schemas in this harness use: ``type``, ``properties``, ``required``,
``additionalProperties: false``, ``enum``, ``items`` and ``minimum``. The validator returns
a list of human-readable problems instead of raising so the loop can hand them back to the
agent as a tool error.
"""

from __future__ import annotations

from typing import Any

_TYPE_CHECKS: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected in ("integer", "number") and isinstance(value, bool):
        return False  # bool is an int subclass in Python; JSON does not agree
    return isinstance(value, _TYPE_CHECKS[expected])


def validate(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Return a list of validation problems (empty when ``value`` conforms)."""
    problems: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_type_ok(value, t) for t in allowed):
            got = type(value).__name__
            problems.append(f"{path}: expected {'/'.join(allowed)}, got {got}")
            return problems
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if "minimum" in schema and isinstance(value, int | float) and value < schema["minimum"]:
        problems.append(f"{path}: {value} is below minimum {schema['minimum']}")
    if isinstance(value, dict):
        props: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}: missing required key '{key}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    problems.append(f"{path}: unknown key '{key}'")
        for key, sub in props.items():
            if key in value:
                problems.extend(validate(value[key], sub, f"{path}.{key}"))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            problems.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return problems
