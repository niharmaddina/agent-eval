"""Deterministic replay providers so the whole suite runs offline.

``scripted`` follows each task's ``script`` exactly (including the recovery steps written
into tier-3 scripts). ``scripted_flawed`` models two common agent failures: on scripts with
three or more tool calls it drops the last tool call before the final answer, and after any
tool error it gives up instead of recovering. Neither is a model; both are baselines that
exercise the harness and give the report a non-trivial failure breakdown.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from agent_eval.providers.base import estimate_message_tokens, estimate_tokens
from agent_eval.types import Message, ProviderResponse, ToolCall, ToolResult, Usage

if TYPE_CHECKING:
    from agent_eval.tasks import Task

_PLACEHOLDER = re.compile(r"\{(last|r\d+)\}")


def render_answer(template: str, results: list[ToolResult]) -> str:
    """Fill ``{last}`` / ``{rN}`` with tool output so answers depend on what the tools said."""
    ok = [r.content for r in results if not r.is_error]

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key == "last":
            return ok[-1] if ok else "unknown"
        idx = int(key[1:])
        return ok[idx] if idx < len(ok) else "unknown"

    return _PLACEHOLDER.sub(sub, template)


def flawed_script(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop the last tool call before the first answer when the script has >= 3 calls."""
    call_idx = [i for i, s in enumerate(steps) if "call" in s]
    first_answer = next((i for i, s in enumerate(steps) if "answer" in s), len(steps))
    before = [i for i in call_idx if i < first_answer]
    if len(call_idx) < 3 or not before:
        return list(steps)
    drop = before[-1]
    return [s for i, s in enumerate(steps) if i != drop]


class ScriptedProvider:
    def __init__(self, flawed: bool = False) -> None:
        self.flawed = flawed
        self.name = "scripted_flawed" if flawed else "scripted"
        self.model = "replay-v1"
        self._steps: list[dict[str, Any]] = []

    def start_task(self, task: Task) -> None:
        self._steps = flawed_script(task.script) if self.flawed else list(task.script)

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> ProviderResponse:
        results = [r for m in messages if m.role == "tool" for r in m.tool_results]
        turn = sum(1 for m in messages if m.role == "assistant")
        in_tokens = estimate_message_tokens(messages, tools)

        if self.flawed and results and results[-1].is_error:
            text = f"I could not complete the task because a tool failed: {results[-1].content}"
            return self._text(text, in_tokens)
        if turn >= len(self._steps):
            return self._text("Done.", in_tokens)
        step = self._steps[turn]
        if "answer" in step:
            return self._text(render_answer(str(step["answer"]), results), in_tokens)
        call = step["call"]
        tc = ToolCall(
            id=f"call_{turn + 1}", name=call["tool"], arguments=dict(call.get("args", {}))
        )
        out = estimate_tokens(tc.name + json.dumps(tc.arguments, sort_keys=True))
        msg = Message("assistant", "", tool_calls=[tc])
        return ProviderResponse(msg, Usage(in_tokens, out, estimated=True), "tool_use")

    @staticmethod
    def _text(text: str, in_tokens: int) -> ProviderResponse:
        usage = Usage(in_tokens, estimate_tokens(text), estimated=True)
        return ProviderResponse(Message("assistant", text), usage, "end_turn")
