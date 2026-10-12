"""Provider protocol and shared helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from agent_eval.types import Message, ProviderResponse

if TYPE_CHECKING:
    from agent_eval.tasks import Task


class ProviderError(Exception):
    """The provider failed to produce a response (network, HTTP error, bad payload)."""


class ProviderUnavailable(ProviderError):
    """The provider cannot be constructed in this environment (missing key or package)."""


class Provider(Protocol):
    name: str
    model: str

    def start_task(self, task: Task) -> None:
        """Called once before each task; real-model providers ignore it."""

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> ProviderResponse:
        """Produce the next assistant message given the full conversation and tool specs."""


def estimate_tokens(text: str) -> int:
    """Rough, deterministic token estimate (about four characters per token)."""
    return max(1, len(text) // 4)


def estimate_message_tokens(messages: list[Message], tools: list[dict[str, Any]]) -> int:
    total = estimate_tokens(json.dumps(tools, sort_keys=True))
    for m in messages:
        total += estimate_tokens(m.content)
        for c in m.tool_calls:
            total += estimate_tokens(c.name + json.dumps(c.arguments, sort_keys=True))
        for r in m.tool_results:
            total += estimate_tokens(r.content)
    return total
