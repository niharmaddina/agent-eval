"""Task suite loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_eval.tasks.checkers import run_checks, validate_check
from agent_eval.tools import ALL_TOOLS
from agent_eval.types import Budget

# Default tier labels; a suite file may declare its own ``tiers:`` mapping instead.
TIERS = {1: "single tool", 2: "multi-step", 3: "error recovery"}
KNOWN_TOOLS = frozenset(t.name for t in ALL_TOOLS)
SUITES_DIR = Path(__file__).parent
DEFAULT_SUITE = SUITES_DIR / "basic.yaml"
RESEARCH_SUITE = SUITES_DIR / "research.yaml"


@dataclass
class Task:
    id: str
    tier: int
    prompt: str
    checks: list[dict[str, Any]]
    script: list[dict[str, Any]]
    script_flawed: list[dict[str, Any]] | None = None  # explicit flawed replay, if declared
    tools: list[str] | None = None
    budget: Budget = field(default_factory=Budget)
    setup_files: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Suite:
    name: str
    version: int
    tasks: list[Task]
    tiers: dict[int, str] = field(default_factory=lambda: dict(TIERS))

    def by_tier(self, tier: int) -> list[Task]:
        return [t for t in self.tasks if t.tier == tier]


def _check_script(task_id: str, key: str, script: Any) -> list[dict[str, Any]]:
    if not isinstance(script, list) or not script:
        raise ValueError(f"task {task_id}: '{key}' must be a non-empty list of steps")
    for step in script:
        if not isinstance(step, dict) or ("call" in step) == ("answer" in step):
            raise ValueError(f"task {task_id}: {key} step needs exactly one of call/answer")
        call = step.get("call")
        if call is not None and (
            not isinstance(call, dict)
            or not isinstance(call.get("tool"), str)
            or not isinstance(call.get("args", {}), dict)
        ):
            raise ValueError(f"task {task_id}: {key} call needs 'tool' and mapping 'args'")
    return list(script)


def _parse_tiers(raw: Any) -> dict[int, str]:
    if raw is None:
        return dict(TIERS)
    if not isinstance(raw, dict) or not raw:
        raise ValueError("suite 'tiers' must be a non-empty mapping of number -> label")
    tiers: dict[int, str] = {}
    for key, label in raw.items():
        if not isinstance(key, int) or isinstance(key, bool) or not isinstance(label, str):
            raise ValueError(f"suite 'tiers': expected integer -> string, got {key!r}: {label!r}")
        tiers[key] = label
    return dict(sorted(tiers.items()))


def _parse_tools(raw: Any, where: str) -> list[str] | None:
    if not raw:
        return None
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        raise ValueError(f"{where}: 'tools' must be a list of tool names")
    unknown = [t for t in raw if t not in KNOWN_TOOLS]
    if unknown:
        raise ValueError(f"{where}: unknown tools {unknown}")
    return list(raw)


def _parse_task(
    raw: dict[str, Any], tiers: dict[int, str], default_tools: list[str] | None
) -> Task:
    for key in ("id", "tier", "prompt", "check", "script"):
        if key not in raw:
            raise ValueError(f"task {raw.get('id', '?')}: missing '{key}'")
    if raw["tier"] not in tiers:
        raise ValueError(f"task {raw['id']}: tier must be one of {sorted(tiers)}")
    if not raw["check"]:
        raise ValueError(f"task {raw['id']}: needs at least one check")
    for check in raw["check"]:
        if not isinstance(check, dict) or len(check) != 1:
            raise ValueError(f"task {raw['id']}: a check is a one-key mapping, got {check!r}")
        kind, arg = next(iter(check.items()))
        problem = validate_check(kind, arg)
        if problem:
            raise ValueError(f"task {raw['id']}: {problem}")
    script = _check_script(raw["id"], "script", raw["script"])
    flawed = raw.get("script_flawed")
    if flawed is not None:
        flawed = _check_script(raw["id"], "script_flawed", flawed)
    tools = _parse_tools(raw.get("tools"), f"task {raw['id']}") or default_tools
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
        script=script,
        script_flawed=flawed,
        tools=tools,
        budget=budget,
        setup_files=dict(raw.get("setup", {}).get("files", {})),
        notes=str(raw.get("notes", "")),
    )


def load_suite(path: Path | str = DEFAULT_SUITE) -> Suite:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError("suite file must be a mapping with a 'tasks' list")
    tiers = _parse_tiers(data.get("tiers"))
    default_tools = _parse_tools(data.get("tools"), "suite")  # applies to tasks without tools:
    tasks = [_parse_task(t, tiers, default_tools) for t in data["tasks"]]
    ids = [t.id for t in tasks]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate task ids: {dupes}")
    return Suite(
        name=str(data.get("suite", "unnamed")),
        version=int(data.get("version", 1)),
        tasks=tasks,
        tiers=tiers,
    )


__all__ = [
    "DEFAULT_SUITE",
    "KNOWN_TOOLS",
    "RESEARCH_SUITE",
    "SUITES_DIR",
    "TIERS",
    "Suite",
    "Task",
    "load_suite",
    "run_checks",
]
