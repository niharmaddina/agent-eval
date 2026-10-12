"""Render metrics as a markdown report and a JSON document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPLAY_NOTE = (
    "This run used a deterministic replay provider. The numbers describe the harness and the "
    "task suite, not any language model."
)


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _cost(c: float | None) -> str:
    return "n/a (model not in price table)" if c is None else f"${c:.4f}"


def _row(cells: list[Any]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render_markdown(meta: dict[str, Any], metrics: dict[str, Any]) -> str:
    o = metrics["overall"]
    token_note = "estimated (len/4 heuristic)" if o["tokens_estimated"] else "reported by the API"
    lines = [
        f"# agent-eval report: `{meta['provider']}` ({meta['model']})",
        "",
        f"- Suite: `{meta['suite']}` v{meta['suite_version']} ({o['total']} tasks)",
        f"- Generated: {meta['generated_at']}",
        f"- Token counts: {token_note}",
        f"- Estimated cost: {_cost(o['estimated_cost_usd'])}",
    ]
    if meta["provider"].startswith("scripted"):
        lines.append(f"- Baseline note: {REPLAY_NOTE}")
    lines += [
        "",
        "## Summary by tier",
        "",
        _row(
            [
                "Tier",
                "What it measures",
                "Tasks",
                "Passed",
                "Success",
                "Mean steps",
                "Tool calls",
                "Tool errors",
                "Tool error rate",
                "Validation errors",
            ]
        ),
        _row(["---"] * 10),
    ]
    for t in metrics["tiers"]:
        lines.append(
            _row(
                [
                    t["tier"],
                    t["label"],
                    t["total"],
                    t["passed"],
                    _pct(t["success_rate"]),
                    t["mean_steps"],
                    t["tool_calls"],
                    t["tool_errors"],
                    _pct(t["tool_error_rate"]),
                    t["validation_errors"],
                ]
            )
        )
    lines.append(
        _row(
            [
                "all",
                "",
                o["total"],
                o["passed"],
                _pct(o["success_rate"]),
                o["mean_steps"],
                o["tool_calls"],
                o["tool_errors"],
                _pct(o["tool_error_rate"]),
                o["validation_errors"],
            ]
        )
    )
    lines += [
        "",
        f"Tokens: {o['input_tokens']} in / {o['output_tokens']} out.",
        "",
        "## Failure breakdown",
        "",
    ]
    if metrics["failures"]:
        lines += [_row(["Category", "Count"]), _row(["---", "---"])]
        lines += [_row([k, v]) for k, v in metrics["failures"].items()]
    else:
        lines.append("No failures.")
    lines += [
        "",
        "## Per task",
        "",
        _row(["Task", "Tier", "Result", "Steps", "Tool calls", "Tool errors", "Stop", "Detail"]),
        _row(["---"] * 8),
    ]
    for t in metrics["tasks"]:
        detail = t["failure_category"] or ""
        if t["failures"]:
            detail += ": " + t["failures"][0][:90].replace("|", "/").replace("\n", " ")
        lines.append(
            _row(
                [
                    f"`{t['task_id']}`",
                    t["tier"],
                    "pass" if t["passed"] else "FAIL",
                    t["steps"],
                    t["tool_calls"],
                    t["tool_errors"],
                    t["stop_reason"],
                    detail,
                ]
            )
        )
    return "\n".join(lines) + "\n"


def write_report(
    out_dir: Path, meta: dict[str, Any], metrics: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transcripts").mkdir(exist_ok=True)
    for rec in records:
        (out_dir / "transcripts" / f"{rec['task_id']}.json").write_text(
            json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    json_path = out_dir / "results.json"
    json_path.write_text(
        json.dumps({"meta": meta, **metrics}, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    md_path = out_dir / "report.md"
    md_path.write_text(render_markdown(meta, metrics), encoding="utf-8")
    return json_path, md_path
