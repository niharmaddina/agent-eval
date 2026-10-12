"""Aggregate run records into per-tier and overall metrics plus a failure breakdown."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_eval.tasks import TIERS, Suite
from agent_eval.types import RunRecord, Usage

# USD per 1M tokens (input, output). Anthropic list prices as cached in the claude-api
# reference on 2026-06-24; verify against the live pricing page before relying on a figure.
# The replay providers make no API calls, so their price is zero by definition.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "replay-v1": (0.0, 0.0),
}


def estimate_cost(model: str, usage: Usage) -> float | None:
    """Return estimated USD for ``usage`` or None when the model is not in the price table."""
    price = PRICES_PER_MTOK.get(model)
    if price is None:
        return None
    return round((usage.input_tokens * price[0] + usage.output_tokens * price[1]) / 1_000_000, 6)


def _answered_right_after_error(rec: RunRecord) -> bool:
    """True when the last tool result was an error and no further tool call followed it."""
    last_result = next((e for e in reversed(rec.transcript) if e["type"] == "tool_result"), None)
    return bool(last_result and last_result["is_error"])


def failure_category(rec: RunRecord) -> str | None:
    if rec.passed:
        return None
    if rec.stop_reason != "answered":
        return rec.stop_reason
    if _answered_right_after_error(rec):
        return "gave_up_after_error"
    kinds = {f.split(":", 1)[0] for f in rec.failures}
    if kinds == {"answer"}:
        return "wrong_answer"
    if kinds == {"state"}:
        return "wrong_state"
    if kinds == {"answer", "state"}:
        return "wrong_answer_and_state"
    return "checker_error"


def _aggregate(records: list[RunRecord], model: str) -> dict[str, Any]:
    n = len(records)
    usage = Usage()
    for r in records:
        usage.add(r.usage)
    passed = sum(r.passed for r in records)
    calls = sum(r.tool_calls for r in records)
    errors = sum(r.tool_errors for r in records)
    return {
        "total": n,
        "passed": passed,
        "success_rate": round(passed / n, 4) if n else 0.0,
        "mean_steps": round(sum(r.steps for r in records) / n, 2) if n else 0.0,
        "tool_calls": calls,
        "tool_errors": errors,
        "tool_error_rate": round(errors / calls, 4) if calls else 0.0,
        "validation_errors": sum(r.validation_errors for r in records),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "tokens_estimated": usage.estimated,
        "estimated_cost_usd": estimate_cost(model, usage),
    }


def compute_metrics(records: list[RunRecord], suite: Suite, model: str) -> dict[str, Any]:
    tier_of = {t.id: t.tier for t in suite.tasks}
    tiers = []
    for tier, label in sorted(TIERS.items()):
        subset = [r for r in records if tier_of.get(r.task_id) == tier]
        if subset:
            tiers.append({"tier": tier, "label": label, **_aggregate(subset, model)})
    failures = Counter(c for r in records if (c := failure_category(r)) is not None)
    stops = Counter(r.stop_reason for r in records)
    tasks = [
        {
            "task_id": r.task_id,
            "tier": tier_of.get(r.task_id),
            "passed": r.passed,
            "steps": r.steps,
            "tool_calls": r.tool_calls,
            "tool_errors": r.tool_errors,
            "validation_errors": r.validation_errors,
            "stop_reason": r.stop_reason,
            "failure_category": failure_category(r),
            "failures": r.failures,
            "tokens": r.usage.total,
        }
        for r in records
    ]
    return {
        "overall": _aggregate(records, model),
        "tiers": tiers,
        "failures": dict(sorted(failures.items())),
        "stop_reasons": dict(sorted(stops.items())),
        "tasks": tasks,
    }
