"""Task suite loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_eval.tasks.checkers import CHECK_KINDS, run_checks
from agent_eval.types import Budget

TIERS = {1: "single tool", 2: "multi-step", 3: "error recovery"}
DEFAULT_SUITE = Path(__file__).parent / "basic.yaml"


@dataclass
class Task:
    id: str
    tier: int
    prompt: str
    checks: list[dict[str, Any]]
    script: list[dict[str, Any]]
    tools: list[str] | None = None
    budget: Budget = field(default_factory=Budget)
    setup_files: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Suite:
    name: str
    version: int
    tasks: list[Task]

    def by_tier(self, tier: int) -> list[Task]:
        return [t for t in self.tasks if t.tier == tier]


def _parse_task(raw: dict[str, Any]) -> Task:
    for key in ("id", "tier", "prompt", "check", "script"):
        if key not in raw:
            raise ValueError(f"task {raw.get('id', '?')}: missing '{key}'")
    if raw["tier"] not in TIERS:
        raise ValueError(f"task {raw['id']}: tier must be one of {sorted(TIERS)}")
    for check in raw["check"]:
        if len(check) != 1 or next(iter(check)) not in CHECK_KINDS:
            raise ValueError(f"task {raw['id']}: bad check {check!r}")
    for step in raw["script"]:
        if ("call" in step) == ("answer" in step):
            raise ValueError(f"task {raw['id']}: script step needs exactly one of call/answer")
    budget_raw = raw.get("budget", {})
    budget = Budget(
        max_steps=int(budget_raw.get("max_steps", Budget.max_steps)),
        max_tokens=int(budget_raw.get("max_tokens", Budget.max_tokens)),
    )
    return Task(
        id=str(raw["id"]),
        tier=int(raw["tier"]),
        prompt=str(raw["prompt"]).strip(),
        checks=list(raw["check"]),
        script=list(raw["script"]),
        tools=list(raw["tools"]) if raw.get("tools") else None,
        budget=budget,
        setup_files=dict(raw.get("setup", {}).get("files", {})),
        notes=str(raw.get("notes", "")),
    )


def load_suite(path: Path | str = DEFAULT_SUITE) -> Suite:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    tasks = [_parse_task(t) for t in data["tasks"]]
    ids = [t.id for t in tasks]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate task ids: {dupes}")
    return Suite(
        name=str(data.get("suite", "unnamed")), version=int(data.get("version", 1)), tasks=tasks
    )


__all__ = ["DEFAULT_SUITE", "TIERS", "Suite", "Task", "load_suite", "run_checks"]
