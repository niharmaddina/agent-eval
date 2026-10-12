"""Tool declaration shared by every sandbox tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_eval.tools.sandbox import Sandbox


class ToolError(Exception):
    """A domain error the agent is expected to recover from (missing file, 404 ticket...)."""


Executor = Callable[["Sandbox", dict[str, Any]], str]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Executor

    def spec(self) -> dict[str, Any]:
        """Vendor-neutral declaration: name, description and a JSON schema for arguments."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def obj_schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }
