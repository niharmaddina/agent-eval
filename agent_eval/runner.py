"""Run a suite against a provider and write results."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any

from agent_eval import __version__
from agent_eval.agent import run_loop
from agent_eval.metrics import compute_metrics
from agent_eval.providers.base import Provider
from agent_eval.report import write_report
from agent_eval.tasks import Suite, Task, run_checks
from agent_eval.tools import Sandbox, ToolRegistry
from agent_eval.types import RunRecord


def run_task(provider: Provider, task: Task) -> RunRecord:
    sandbox = Sandbox.fresh(task.setup_files)
    registry = ToolRegistry()
    if task.tools:
        registry = registry.subset(task.tools)
    provider.start_task(task)
    record = run_loop(provider, registry, sandbox, task.prompt, task.budget, task_id=task.id)
    record.failures = run_checks(task.checks, sandbox, record.final_answer)
    record.passed = not record.failures
    return record


def generated_at() -> str:
    """UTC timestamp for a run. ``SOURCE_DATE_EPOCH`` pins it so baselines diff byte-for-byte."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    now = dt.datetime.fromtimestamp(int(epoch), dt.UTC) if epoch else dt.datetime.now(dt.UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_suite(
    provider: Provider,
    suite: Suite,
    out_dir: Path,
    only: set[str] | None = None,
    tier: int | None = None,
) -> dict[str, Any]:
    tasks = [
        t
        for t in suite.tasks
        if (only is None or t.id in only) and (tier is None or t.tier == tier)
    ]
    records = [run_task(provider, t) for t in tasks]
    metrics = compute_metrics(records, suite, provider.model)
    meta = {
        "provider": provider.name,
        "model": provider.model,
        "suite": suite.name,
        "suite_version": suite.version,
        "generated_at": generated_at(),
        "agent_eval_version": __version__,
        "is_model_result": not provider.name.startswith("scripted"),
    }
    write_report(out_dir, meta, metrics, [r.to_dict() for r in records])
    return {"meta": meta, **metrics}
