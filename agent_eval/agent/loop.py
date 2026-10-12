"""Bounded, provider-agnostic tool-use loop.

One *step* is one provider call. After each call the loop executes every requested tool
call against the sandbox (validating arguments against the tool's JSON schema first), appends
the results, and asks the provider again. It stops when the provider answers without tool
calls, when the step or token budget is exhausted, or when the provider fails.
"""

from __future__ import annotations

from typing import Any

from agent_eval.providers.base import Provider, ProviderError
from agent_eval.tools import Sandbox, ToolError, ToolRegistry
from agent_eval.tools.schema import validate
from agent_eval.types import Budget, Message, RunRecord, StopReason, ToolCall, ToolResult, Usage

SYSTEM_PROMPT = (
    "You are an agent completing a task inside a sandbox. Use the provided tools to inspect "
    "and change state. Tool errors are returned as text; read them and recover (for example "
    "list a directory when a file is missing, or list tickets when an id is unknown). When the "
    "task is complete, reply with a concise final answer and make no further tool calls."
)


class _Executor:
    def __init__(self, registry: ToolRegistry, sandbox: Sandbox) -> None:
        self.registry = registry
        self.sandbox = sandbox
        self.tool_errors = 0
        self.validation_errors = 0

    def run(self, call: ToolCall) -> ToolResult:
        if call.parse_error:
            self.validation_errors += 1
            return ToolResult(call.id, f"invalid arguments: {call.parse_error}", is_error=True)
        tool = self.registry.get(call.name)
        if tool is None:
            self.validation_errors += 1
            known = ", ".join(self.registry.names())
            return ToolResult(call.id, f"unknown tool '{call.name}'; available: {known}", True)
        problems = validate(call.arguments, tool.input_schema)
        if problems:
            self.validation_errors += 1
            return ToolResult(call.id, "invalid arguments: " + "; ".join(problems), is_error=True)
        try:
            return ToolResult(call.id, tool.execute(self.sandbox, call.arguments))
        except ToolError as exc:
            self.tool_errors += 1
            return ToolResult(call.id, f"error: {exc}", is_error=True)


def run_loop(
    provider: Provider,
    registry: ToolRegistry,
    sandbox: Sandbox,
    prompt: str,
    budget: Budget,
    task_id: str = "adhoc",
    system_prompt: str = SYSTEM_PROMPT,
) -> RunRecord:
    messages = [Message("system", system_prompt), Message("user", prompt)]
    specs = registry.specs()
    executor = _Executor(registry, sandbox)
    transcript: list[dict[str, Any]] = []
    usage = Usage()
    stop: StopReason = "step_budget"
    final_answer = ""
    steps = 0
    n_calls = 0

    for step in range(1, budget.max_steps + 1):
        steps = step
        try:
            response = provider.complete(messages, specs)
        except ProviderError as exc:
            transcript.append({"step": step, "type": "provider_error", "error": str(exc)})
            stop = "provider_error"
            break
        usage.add(response.usage)
        msg = response.message
        messages.append(msg)
        transcript.append(
            {
                "step": step,
                "type": "assistant",
                "text": msg.content,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "args": c.arguments} for c in msg.tool_calls
                ],
                "provider_stop_reason": response.stop_reason,
                "usage": {"in": response.usage.input_tokens, "out": response.usage.output_tokens},
            }
        )
        if response.stop_reason == "refusal":
            stop, final_answer = "refusal", msg.content
            break
        if not msg.tool_calls:
            final_answer = msg.content
            stop = "truncated" if response.stop_reason == "max_tokens" else "answered"
            break
        results: list[ToolResult] = []
        for call in msg.tool_calls:
            n_calls += 1
            result = executor.run(call)
            results.append(result)
            transcript.append(
                {
                    "step": step,
                    "type": "tool_result",
                    "call_id": call.id,
                    "tool": call.name,
                    "is_error": result.is_error,
                    "content": result.content,
                }
            )
        messages.append(Message("tool", tool_results=results))
        if usage.total > budget.max_tokens:
            stop = "token_budget"
            break

    return RunRecord(
        task_id=task_id,
        provider=provider.name,
        model=provider.model,
        stop_reason=stop,
        final_answer=final_answer,
        steps=steps,
        tool_calls=n_calls,
        tool_errors=executor.tool_errors,
        validation_errors=executor.validation_errors,
        usage=usage,
        transcript=transcript,
    )
