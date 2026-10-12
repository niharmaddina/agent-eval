"""Programmatic checks over the sandbox's final state and the agent's final answer.

Each check is a one-key mapping from the task YAML. Failure strings are prefixed with
``state:`` or ``answer:`` so metrics can bucket them.
"""

from __future__ import annotations

import re
from typing import Any

from agent_eval.tools import Sandbox, ToolError

CHECK_KINDS = {
    "file_equals",
    "file_contains",
    "file_absent",
    "file_line_count",
    "answer_contains",
    "answer_not_contains",
    "answer_matches",
    "ticket_field",
    "ticket_note_contains",
    "ticket_note_count",
}


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
        if not re.search(arg, answer, re.IGNORECASE | re.DOTALL):
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
    failures: list[str] = []
    for check in checks:
        for kind, arg in check.items():
            msg = run_check(kind, arg, sb, answer)
            if msg:
                failures.append(msg)
    return failures
