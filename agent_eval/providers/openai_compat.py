"""Chat-completions provider for OpenAI-compatible endpoints (enabled only with OPENAI_API_KEY).

``OPENAI_BASE_URL`` is honoured by the SDK, so local servers that speak the same protocol work
too. The model id must be given via ``AGENT_EVAL_OPENAI_MODEL``; nothing is assumed.
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

from agent_eval.providers.base import ProviderError, ProviderUnavailable, estimate_message_tokens
from agent_eval.types import Message, ProviderResponse, ToolCall, Usage

if TYPE_CHECKING:
    import openai

    from agent_eval.tasks import Task


def to_openai(messages: list[Message]) -> list[Any]:
    out: list[Any] = []
    for m in messages:
        if m.role in ("system", "user"):
            out.append({"role": m.role, "content": m.content})
        elif m.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m.tool_calls
                ]
            out.append(entry)
        else:
            out.extend(
                {"role": "tool", "tool_call_id": r.call_id, "content": r.content}
                for r in m.tool_results
            )
    return out


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, model: str | None = None, client: openai.OpenAI | None = None) -> None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderUnavailable(
                "OPENAI_API_KEY is not set; the openai_compat provider is off"
            )
        try:
            import openai
        except ImportError as exc:
            raise ProviderUnavailable("install with: pip install 'agent-eval[openai]'") from exc
        self.model = model or os.environ.get("AGENT_EVAL_OPENAI_MODEL", "")
        if not self.model:
            raise ProviderUnavailable("set AGENT_EVAL_OPENAI_MODEL to the model id to evaluate")
        self._sdk = openai
        self._client = client if client is not None else openai.OpenAI()

    def start_task(self, task: Task) -> None:
        return None

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> ProviderResponse:
        api_tools: list[Any] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        started = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model, messages=to_openai(messages), tools=api_tools
            )
        except self._sdk.APIError as exc:
            raise ProviderError(f"openai_compat: {exc}") from exc
        latency_ms = round((time.perf_counter() - started) * 1000, 1)

        choice = resp.choices[0]
        calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments or "{}")
                calls.append(ToolCall(tc.id, fn.name, args if isinstance(args, dict) else {}))
            except json.JSONDecodeError as exc:
                calls.append(
                    ToolCall(tc.id, fn.name, {}, parse_error=f"non-JSON arguments ({exc})")
                )
        msg = Message("assistant", choice.message.content or "", tool_calls=calls)
        if resp.usage is not None:
            usage = Usage(resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0)
        else:
            usage = Usage(estimate_message_tokens(messages, tools), 0, estimated=True)
        stop: str = choice.finish_reason or "stop"
        if stop == "length":
            stop = "max_tokens"
        return ProviderResponse(msg, usage, stop_reason=stop, latency_ms=latency_ms)
