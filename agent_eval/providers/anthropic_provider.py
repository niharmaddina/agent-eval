"""Claude provider using the official ``anthropic`` SDK (enabled only with ANTHROPIC_API_KEY).

Refusals are reported as refusals rather than routed to a fallback model: an evaluation run
should attribute every outcome to the model under test.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from agent_eval.providers.base import ProviderError, ProviderUnavailable
from agent_eval.types import Message, ProviderResponse, ToolCall, Usage

if TYPE_CHECKING:
    from agent_eval.tasks import Task

DEFAULT_MODEL = "claude-opus-5"


def to_anthropic(messages: list[Message]) -> tuple[str, list[Any]]:
    """Convert the neutral transcript into (system, messages) for the Messages API."""
    system_parts: list[str] = []
    out: list[Any] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            if m.raw is not None:  # echo native blocks (including thinking) unchanged
                out.append({"role": "assistant", "content": m.raw})
                continue
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            blocks.extend(
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m.tool_calls
            )
            out.append({"role": "assistant", "content": blocks})
        else:  # tool results travel in a single user turn
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.call_id,
                            "content": r.content,
                            "is_error": r.is_error,
                        }
                        for r in m.tool_results
                    ],
                }
            )
    return "\n\n".join(system_parts), out


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None, max_output_tokens: int = 4096) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not set; the anthropic provider is off")
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderUnavailable("install with: pip install 'agent-eval[anthropic]'") from exc
        self._sdk = anthropic
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("AGENT_EVAL_ANTHROPIC_MODEL", DEFAULT_MODEL)
        # Eval answers are short by construction; the loop's token budget bounds the whole run.
        self.max_output_tokens = max_output_tokens

    def start_task(self, task: Task) -> None:
        return None

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> ProviderResponse:
        system, api_messages = to_anthropic(messages)
        api_tools: list[Any] = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_output_tokens,
                system=system,
                tools=api_tools,
                messages=api_messages,
            )
        except self._sdk.APIStatusError as exc:
            raise ProviderError(f"anthropic HTTP {exc.status_code}: {exc.message}") from exc
        except self._sdk.APIConnectionError as exc:
            raise ProviderError(f"anthropic connection error: {exc}") from exc

        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
            for b in resp.content
            if b.type == "tool_use"
        ]
        msg = Message("assistant", text, tool_calls=calls, raw=list(resp.content))
        usage = Usage(resp.usage.input_tokens, resp.usage.output_tokens)
        return ProviderResponse(msg, usage, stop_reason=resp.stop_reason or "end_turn")
