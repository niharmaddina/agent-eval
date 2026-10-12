"""Provider-agnostic message and run types shared across the harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    """A request by the agent to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any]
    parse_error: str | None = None  # set when a provider returned non-JSON arguments


@dataclass
class ToolResult:
    """The outcome of executing one tool call."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """One turn in the conversation, independent of any vendor wire format."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    raw: Any = None  # provider-native content blocks, echoed back verbatim when present


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated: bool = False  # True when the provider cannot report real token counts

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.estimated = self.estimated or other.estimated


@dataclass
class ProviderResponse:
    message: Message
    usage: Usage
    stop_reason: str = "end_turn"


@dataclass
class Budget:
    max_steps: int = 10
    max_tokens: int = 20_000


StopReason = Literal[
    "answered", "step_budget", "token_budget", "provider_error", "refusal", "truncated"
]


@dataclass
class RunRecord:
    """Everything the loop knows about one task attempt."""

    task_id: str
    provider: str
    model: str
    stop_reason: StopReason
    final_answer: str
    steps: int
    tool_calls: int
    tool_errors: int
    validation_errors: int
    usage: Usage
    transcript: list[dict[str, Any]]
    passed: bool = False
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "provider": self.provider,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "final_answer": self.final_answer,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "validation_errors": self.validation_errors,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "estimated": self.usage.estimated,
            },
            "passed": self.passed,
            "failures": self.failures,
            "transcript": self.transcript,
        }
