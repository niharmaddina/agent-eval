"""Test doubles shared by the test modules."""

from __future__ import annotations

from typing import Any

from agent_eval.providers.base import ProviderError
from agent_eval.types import Message, ProviderResponse, ToolCall, Usage


class ListProvider:
    """Replays a fixed list of assistant messages; raises when it runs out."""

    name = "fake"
    model = "fake-model"

    def __init__(self, turns: list[Message], stop_reasons: list[str] | None = None) -> None:
        self.turns = turns
        self.stop_reasons = stop_reasons or []
        self.calls = 0
        self.seen: list[list[Message]] = []

    def start_task(self, task: Any) -> None:
        return None

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> ProviderResponse:
        self.seen.append(list(messages))
        if self.calls >= len(self.turns):
            raise ProviderError("script exhausted")
        msg = self.turns[self.calls]
        stop = self.stop_reasons[self.calls] if self.calls < len(self.stop_reasons) else None
        self.calls += 1
        if stop is None:
            stop = "tool_use" if msg.tool_calls else "end_turn"
        return ProviderResponse(msg, Usage(100, 10), stop_reason=stop)


def call(name: str, **args: Any) -> Message:
    return Message("assistant", tool_calls=[ToolCall(id=f"c{name}", name=name, arguments=args)])


def answer(text: str) -> Message:
    return Message("assistant", text)
