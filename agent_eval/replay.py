"""Pretty-print one transcript so a reviewer can read a failure without the JSON.

Each assistant turn is shown with its tool calls, and every call's arguments are re-validated
against the current tool schema (``[args ok]``, ``[args invalid: ...]`` or ``[unknown tool]``)
so a reviewer sees the schema verdict next to the call rather than buried in the tool result.
"""

from __future__ import annotations

import json
from typing import Any

from agent_eval.metrics import failure_category
from agent_eval.tools import ToolRegistry
from agent_eval.tools.schema import validate
from agent_eval.types import RunRecord

RESULT_CHARS = 300
RESULT_LINES = 6


def _clip(text: str, full: bool) -> list[str]:
    """Split a tool result into display lines, truncating unless ``full``."""
    if not full and len(text) > RESULT_CHARS:
        text = text[:RESULT_CHARS] + f"... (+{len(text) - RESULT_CHARS} chars)"
    lines = text.splitlines() or [""]
    if not full and len(lines) > RESULT_LINES:
        lines = [*lines[:RESULT_LINES], f"... (+{len(lines) - RESULT_LINES} lines)"]
    return lines


def _args_verdict(name: str, args: dict[str, Any], registry: ToolRegistry) -> str:
    tool = registry.get(name)
    if tool is None:
        return "[unknown tool]"
    problems = validate(args, tool.input_schema)
    return "[args ok]" if not problems else "[args invalid: " + "; ".join(problems) + "]"


def render_transcript(
    record: dict[str, Any], full: bool = False, registry: ToolRegistry | None = None
) -> str:
    rec = RunRecord.from_dict(record)
    registry = registry or ToolRegistry()
    verdict = "PASS" if rec.passed else "FAIL"
    max_steps = rec.budget.max_steps or "?"
    max_tokens = rec.budget.max_tokens or "?"
    token_note = "estimated" if rec.usage.estimated else "reported by the API"
    latency = "not reported" if rec.latency_ms is None else f"{rec.latency_ms:.0f} ms"
    lines = [
        f"# {rec.task_id} - {rec.provider} ({rec.model}) - {verdict}",
        f"stop: {rec.stop_reason} | steps: {rec.steps}/{max_steps} | tool calls: {rec.tool_calls} "
        f"| tool errors: {rec.tool_errors} | validation errors: {rec.validation_errors}",
        f"tokens: {rec.usage.input_tokens} in / {rec.usage.output_tokens} out = "
        f"{rec.usage.total}/{max_tokens} budget ({token_note}) | latency: {latency}",
        "",
    ]
    calls_by_id: dict[str, str] = {}
    for entry in rec.transcript:
        step = entry.get("step", "?")
        kind = entry.get("type")
        if kind == "provider_error":
            lines.append(f"step {step}  provider error: {entry.get('error', '')}")
        elif kind == "assistant":
            usage = entry.get("usage", {})
            meta = f"{usage.get('in', 0)} in / {usage.get('out', 0)} out"
            if entry.get("latency_ms") is not None:
                meta += f", {entry['latency_ms']:.0f} ms"
            lines.append(
                f"step {step}  assistant ({entry.get('provider_stop_reason', '?')}; {meta})"
            )
            if entry.get("text"):
                lines += [f"  {ln}" for ln in str(entry["text"]).splitlines()]
            for call in entry.get("tool_calls", []):
                args = call.get("args", {})
                calls_by_id[str(call.get("id"))] = str(call.get("name"))
                verdict_txt = _args_verdict(str(call.get("name")), args, registry)
                lines.append(
                    f"  -> {call.get('name')} {json.dumps(args, sort_keys=True)}  {verdict_txt}"
                )
        elif kind == "tool_result":
            tag = "ERROR" if entry.get("is_error") else "ok"
            body = _clip(str(entry.get("content", "")), full)
            lines.append(
                f"  <- {entry.get('tool', calls_by_id.get(str(entry.get('call_id'))))} "
                f"{tag}: {body[0]}"
            )
            lines += [f"     {ln}".rstrip() for ln in body[1:]]
    lines.append("")
    category = failure_category(rec)
    lines.append(f"verdict: {verdict}" + (f" ({category})" if category else ""))
    if rec.failures:
        lines += [f"  - {f}" for f in rec.failures]
    elif not rec.passed:
        lines.append("  - no check failures recorded; the run stopped before an answer")
    return "\n".join(lines) + "\n"
