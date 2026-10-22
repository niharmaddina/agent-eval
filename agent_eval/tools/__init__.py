"""Deterministic tool sandbox: declarations, executors and the registry."""

from __future__ import annotations

from agent_eval.tools.base import Tool, ToolError
from agent_eval.tools.calculator import CALCULATOR_TOOLS
from agent_eval.tools.filesystem import FS_TOOLS
from agent_eval.tools.sandbox import Sandbox
from agent_eval.tools.tickets import TICKET_TOOLS
from agent_eval.tools.web import WEB_TOOLS

ALL_TOOLS: list[Tool] = [*FS_TOOLS, *CALCULATOR_TOOLS, *TICKET_TOOLS, *WEB_TOOLS]


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {
            t.name: t for t in (tools if tools is not None else ALL_TOOLS)
        }

    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def subset(self, names: list[str]) -> ToolRegistry:
        missing = [n for n in names if n not in self._tools]
        if missing:
            raise KeyError(f"unknown tools: {missing}")
        return ToolRegistry([self._tools[n] for n in names])

    def specs(self) -> list[dict[str, object]]:
        return [t.spec() for t in self._tools.values()]


__all__ = ["ALL_TOOLS", "Sandbox", "Tool", "ToolError", "ToolRegistry"]
