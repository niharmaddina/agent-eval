"""Programmatic checks over the sandbox's final state and the agent's final answer.

Each check is a one-key mapping from the task YAML. Failure strings are prefixed with
``state:`` or ``answer:`` so metrics can bucket them.
"""

from __future__ import annotations

import re
from typing import Any

from agent_eval.tools import Sandbox, ToolError

# check kind -> required mapping keys, or None when the argument is a string / list of strings
CHECK_KINDS: dict[str, tuple[str, ...] | None] = {
    "file_equals": ("path", "content"),
    "file_contains": ("path", "text"),
    "file_absent": ("path",),
    "file_line_count": ("path", "equals"),
    "answer_contains": None,
    "answer_not_contains": None,
    "answer_matches": None,
    "ticket_field": ("id", "field", "equals"),
    "ticket_note_contains": ("id", "text"),
    "ticket_note_count": ("id", "equals"),
}


def validate_check(kind: str, arg: Any) -> str | None:
    """Return a problem description for a malformed check, or None when it is well-formed."""
    if kind not in CHECK_KINDS:
        return f"unknown check kind '{kind}' (known: {sorted(CHECK_KINDS)})"
    keys = CHECK_KINDS[kind]
    if keys is None:
        values = arg if isinstance(arg, list) else [arg]
        if not values or not all(isinstance(v, str) and v for v in values):
            return f"{kind}: expected a non-empty string or list of strings, got {arg!r}"
        if kind == "answer_matches":
            if not isinstance(arg, str):
                return f"{kind}: expected a single regex string, got {arg!r}"
            try:
                re.compile(arg)
            except re.error as exc:
                return f"{kind}: invalid regex /{arg}/ ({exc})"
        return None
    if not isinstance(arg, dict):
        return f"{kind}: expected a mapping with keys {list(keys)}, got {arg!r}"
    missing = [k for k in keys if k not in arg]
    if missing:
        return f"{kind}: missing keys {missing}"
    return None


def _file(sb: Sandbox, path: str) -> str | None:
    try:
        return sb.fs.read(path)
    except ToolError:
        return None


def _ticket(sb: Sandbox, tid: str) -> dict[str, Any] | None:
    try:
        return sb.tickets.get(tid)
    except ToolError:
        return None


def run_check(kind: str, arg: Any, sb: Sandbox, answer: str) -> str | None:
    """Return a failure message, or None when the check passes."""
    low = answer.lower()
    if kind == "file_equals":
        got = _file(sb, arg["path"])
        if got != arg["content"]:
            return f"state: {arg['path']} content mismatch (got {got!r})"
    elif kind == "file_contains":
        got = _file(sb, arg["path"])
        if got is None or arg["text"] not in got:
            return f"state: {arg['path']} does not contain {arg['text']!r}"
    elif kind == "file_absent":
        if _file(sb, arg["path"]) is not None:
            return f"state: {arg['path']} should not exist"
    elif kind == "file_line_count":
        got = _file(sb, arg["path"])
        n = len(got.splitlines()) if got is not None else -1
        if n != arg["equals"]:
            return f"state: {arg['path']} has {n} lines, expected {arg['equals']}"
    elif kind == "answer_contains":
        needles = arg if isinstance(arg, list) else [arg]
        missing = [n for n in needles if str(n).lower() not in low]
        if missing:
            return f"answer: missing {missing} in {answer[:120]!r}"
    elif kind == "answer_not_contains":
        needles = arg if isinstance(arg, list) else [arg]
        present = [n for n in needles if str(n).lower() in low]
        if present:
            return f"answer: should not mention {present}"
    elif kind == "answer_matches":
        try:
            pattern = re.compile(arg, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            return f"checker: invalid regex /{arg}/ ({exc})"
        if not pattern.search(answer):
            return f"answer: does not match /{arg}/ in {answer[:120]!r}"
    elif kind == "ticket_field":
        t = _ticket(sb, arg["id"])
        got = t.get(arg["field"]) if t else None
        if got != arg["equals"]:
            return (
                f"state: ticket {arg['id']}.{arg['field']} is {got!r}, expected {arg['equals']!r}"
            )
    elif kind == "ticket_note_contains":
        t = _ticket(sb, arg["id"])
        notes = t.get("notes", []) if t else []
        if not any(arg["text"].lower() in n.lower() for n in notes):
            return f"state: ticket {arg['id']} has no note containing {arg['text']!r}"
    elif kind == "ticket_note_count":
        t = _ticket(sb, arg["id"])
        n = len(t.get("notes", [])) if t else -1
        if n != arg["equals"]:
            return f"state: ticket {arg['id']} has {n} notes, expected {arg['equals']}"
    else:
        return f"checker: unknown check kind '{kind}'"
    return None


def run_checks(checks: list[dict[str, Any]], sb: Sandbox, answer: str) -> list[str]:
    """Run every check; a malformed check is reported as a ``checker:`` failure, never raised."""
    failures: list[str] = []
    for check in checks:
        for kind, arg in check.items():
            try:
                msg = run_check(kind, arg, sb, answer)
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"checker: malformed {kind} check ({type(exc).__name__}: {exc})"
            if msg:
                failures.append(msg)
    return failures
