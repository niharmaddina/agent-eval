"""Diff two result directories of the same suite, task by task.

``A`` is the baseline and ``B`` the candidate. A task is *newly passing* when it failed in A
and passes in B, *newly failing* the other way round. Step and token deltas are B minus A.
Both inputs are ``results.json`` files written by ``agent-eval run``; nothing is re-executed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATUSES = ("newly_passing", "newly_failing", "pass_both", "fail_both", "only_in_a", "only_in_b")


def load_results(path: Path) -> dict[str, Any]:
    """Read ``results.json`` from a directory (or the file itself)."""
    file = path / "results.json" if path.is_dir() else path
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "meta" not in data or "tasks" not in data:
        raise ValueError(f"{file}: not an agent-eval results.json (needs 'meta' and 'tasks')")
    return data


def _status(a: dict[str, Any] | None, b: dict[str, Any] | None) -> str:
    if a is None:
        return "only_in_b"
    if b is None:
        return "only_in_a"
    if a["passed"] != b["passed"]:
        return "newly_passing" if b["passed"] else "newly_failing"
    return "pass_both" if a["passed"] else "fail_both"


def _mean(values: list[int]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ma, mb = a["meta"], b["meta"]
    if ma["suite"] != mb["suite"]:
        raise ValueError(f"suites differ: A is {ma['suite']!r}, B is {mb['suite']!r}")
    tasks_a = {t["task_id"]: t for t in a["tasks"]}
    tasks_b = {t["task_id"]: t for t in b["tasks"]}
    order = list(tasks_a) + [tid for tid in tasks_b if tid not in tasks_a]
    rows: list[dict[str, Any]] = []
    for tid in order:
        ta, tb = tasks_a.get(tid), tasks_b.get(tid)
        ref: dict[str, Any] = ta or tb or {}
        status = _status(ta, tb)
        row: dict[str, Any] = {"task_id": tid, "tier": ref["tier"], "status": status}
        if ta is not None and tb is not None:
            row.update(
                passed_a=ta["passed"],
                passed_b=tb["passed"],
                steps_a=ta["steps"],
                steps_b=tb["steps"],
                steps_delta=tb["steps"] - ta["steps"],
                tokens_a=ta["tokens"],
                tokens_b=tb["tokens"],
                tokens_delta=tb["tokens"] - ta["tokens"],
                stop_a=ta["stop_reason"],
                stop_b=tb["stop_reason"],
                failure_a=ta.get("failure_category"),
                failure_b=tb.get("failure_category"),
                detail_b=(tb.get("failures") or [""])[0],
            )
        rows.append(row)

    common = [r for r in rows if r["status"] not in ("only_in_a", "only_in_b")]
    labels = {t["tier"]: t["label"] for t in [*a.get("tiers", []), *b.get("tiers", [])]}
    tiers = []
    for tier in sorted({r["tier"] for r in common}):
        sub = [r for r in common if r["tier"] == tier]
        tiers.append(
            {
                "tier": tier,
                "label": labels.get(tier, ""),
                "total": len(sub),
                "passed_a": sum(r["passed_a"] for r in sub),
                "passed_b": sum(r["passed_b"] for r in sub),
                "passed_delta": sum(r["passed_b"] for r in sub) - sum(r["passed_a"] for r in sub),
                "newly_passing": sum(r["status"] == "newly_passing" for r in sub),
                "newly_failing": sum(r["status"] == "newly_failing" for r in sub),
                "mean_steps_a": _mean([r["steps_a"] for r in sub]),
                "mean_steps_b": _mean([r["steps_b"] for r in sub]),
                "tokens_a": sum(r["tokens_a"] for r in sub),
                "tokens_b": sum(r["tokens_b"] for r in sub),
            }
        )
    summary = {
        "common_tasks": len(common),
        "only_in_a": sum(r["status"] == "only_in_a" for r in rows),
        "only_in_b": sum(r["status"] == "only_in_b" for r in rows),
        "passed_a": sum(r["passed_a"] for r in common),
        "passed_b": sum(r["passed_b"] for r in common),
        "newly_passing": sum(r["status"] == "newly_passing" for r in common),
        "newly_failing": sum(r["status"] == "newly_failing" for r in common),
        "pass_both": sum(r["status"] == "pass_both" for r in common),
        "fail_both": sum(r["status"] == "fail_both" for r in common),
        "steps_a": sum(r["steps_a"] for r in common),
        "steps_b": sum(r["steps_b"] for r in common),
        "tokens_a": sum(r["tokens_a"] for r in common),
        "tokens_b": sum(r["tokens_b"] for r in common),
        "cost_a": a["overall"].get("estimated_cost_usd"),
        "cost_b": b["overall"].get("estimated_cost_usd"),
    }
    summary["passed_delta"] = summary["passed_b"] - summary["passed_a"]
    summary["steps_delta"] = summary["steps_b"] - summary["steps_a"]
    summary["tokens_delta"] = summary["tokens_b"] - summary["tokens_a"]
    return {"a": ma, "b": mb, "summary": summary, "tiers": tiers, "tasks": rows}


def _signed(n: int | float) -> str:
    return f"{n:+}" if n else "0"


def _row(cells: list[Any]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _cost(c: float | None) -> str:
    return "n/a" if c is None else f"${c:.4f}"


def _label(meta: dict[str, Any]) -> str:
    return f"`{meta['provider']}` ({meta['model']})"


def render_markdown(cmp: dict[str, Any], all_tasks: bool = False) -> str:
    s, a, b = cmp["summary"], cmp["a"], cmp["b"]
    lines = [
        f"# agent-eval compare: A = {_label(a)} -> B = {_label(b)}",
        "",
        f"- Suite: `{a['suite']}` v{a['suite_version']} ({s['common_tasks']} tasks in both runs)",
        f"- A generated {a['generated_at']}; B generated {b['generated_at']}",
        f"- Passed: {s['passed_a']} -> {s['passed_b']} ({_signed(s['passed_delta'])}); "
        f"newly passing {s['newly_passing']}, newly failing {s['newly_failing']}, "
        f"unchanged {s['pass_both']} pass / {s['fail_both']} fail",
        f"- Steps: {s['steps_a']} -> {s['steps_b']} ({_signed(s['steps_delta'])}); "
        f"tokens: {s['tokens_a']} -> {s['tokens_b']} ({_signed(s['tokens_delta'])}); "
        f"cost: {_cost(s['cost_a'])} -> {_cost(s['cost_b'])}",
    ]
    if s["only_in_a"] or s["only_in_b"]:
        lines.append(
            f"- Tasks present in one run only: {s['only_in_a']} only in A, "
            f"{s['only_in_b']} only in B"
        )
    lines += [
        "",
        "## By tier",
        "",
        _row(
            [
                "Tier",
                "Label",
                "Tasks",
                "Passed A",
                "Passed B",
                "Delta",
                "Newly passing",
                "Newly failing",
                "Mean steps A",
                "Mean steps B",
                "Tokens A",
                "Tokens B",
            ]
        ),
        _row(["---"] * 12),
    ]
    for t in cmp["tiers"]:
        lines.append(
            _row(
                [
                    t["tier"],
                    t["label"],
                    t["total"],
                    t["passed_a"],
                    t["passed_b"],
                    _signed(t["passed_delta"]),
                    t["newly_passing"],
                    t["newly_failing"],
                    t["mean_steps_a"],
                    t["mean_steps_b"],
                    t["tokens_a"],
                    t["tokens_b"],
                ]
            )
        )
    for status, title in (("newly_failing", "Newly failing"), ("newly_passing", "Newly passing")):
        rows = [r for r in cmp["tasks"] if r["status"] == status]
        lines += ["", f"## {title} ({len(rows)})", ""]
        if not rows:
            lines.append("None.")
            continue
        lines += [
            _row(["Task", "Tier", "Steps A -> B", "Tokens A -> B", "Stop B", "B failure"]),
            _row(["---"] * 6),
        ]
        for r in rows:
            detail = r["failure_b"] or ""
            if r["detail_b"]:
                detail += ": " + r["detail_b"][:90].replace("|", "\\|").replace("\n", " ")
            lines.append(
                _row(
                    [
                        f"`{r['task_id']}`",
                        r["tier"],
                        f"{r['steps_a']} -> {r['steps_b']} ({_signed(r['steps_delta'])})",
                        f"{r['tokens_a']} -> {r['tokens_b']} ({_signed(r['tokens_delta'])})",
                        r["stop_b"],
                        detail,
                    ]
                )
            )
    if all_tasks:
        lines += [
            "",
            "## All tasks",
            "",
            _row(["Task", "Tier", "Status", "Steps A -> B", "Tokens A -> B"]),
            _row(["---"] * 5),
        ]
        for r in cmp["tasks"]:
            if r["status"] in ("only_in_a", "only_in_b"):
                lines.append(_row([f"`{r['task_id']}`", r["tier"], r["status"], "", ""]))
                continue
            lines.append(
                _row(
                    [
                        f"`{r['task_id']}`",
                        r["tier"],
                        r["status"],
                        f"{r['steps_a']} -> {r['steps_b']} ({_signed(r['steps_delta'])})",
                        f"{r['tokens_a']} -> {r['tokens_b']} ({_signed(r['tokens_delta'])})",
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def write_compare(out_dir: Path, cmp: dict[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "compare.json"
    json_path.write_text(json.dumps(cmp, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    md_path = out_dir / "compare.md"
    md_path.write_text(render_markdown(cmp, all_tasks=True), encoding="utf-8")
    return json_path, md_path
