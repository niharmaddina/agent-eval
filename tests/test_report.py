import json

from agent_eval.cli import main
from agent_eval.metrics import compute_metrics, estimate_cost
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.report import REPLAY_NOTE, render_markdown
from agent_eval.runner import run_suite, run_task
from agent_eval.tasks import DEFAULT_SUITE, load_suite
from agent_eval.types import Usage

SUITE = load_suite(DEFAULT_SUITE)
IDS = ["t1_read_readme", "t2_summary_file", "t3_missing_file"]


def test_estimate_cost_uses_price_table():
    assert estimate_cost("claude-opus-5", Usage(1_000_000, 100_000)) == 7.5
    assert estimate_cost("replay-v1", Usage(5000, 500)) == 0.0
    assert estimate_cost("some-unknown-model", Usage(1, 1)) is None


def test_metrics_tiers_and_failure_breakdown():
    flawed = ScriptedProvider(flawed=True)
    records = [run_task(flawed, t) for t in SUITE.tasks if t.id in IDS]
    m = compute_metrics(records, SUITE, flawed.model)
    assert [t["tier"] for t in m["tiers"]] == [1, 2, 3]
    assert m["overall"]["total"] == 3 and m["overall"]["passed"] == 1
    assert m["failures"] == {"gave_up_after_error": 1, "wrong_state": 1}
    assert m["overall"]["tokens_estimated"] is True
    assert m["overall"]["estimated_cost_usd"] == 0.0
    assert m["tiers"][2]["tool_error_rate"] == 1.0


def test_markdown_and_json_outputs(tmp_path):
    good = ScriptedProvider()
    result = run_suite(good, SUITE, tmp_path / "out", only=set(IDS))
    md = (tmp_path / "out" / "report.md").read_text()
    assert md.startswith("# agent-eval report: `scripted` (replay-v1)")
    assert REPLAY_NOTE in md and "| all |" in md and "| `t3_missing_file` | 3 | pass |" in md
    data = json.loads((tmp_path / "out" / "results.json").read_text())
    assert data["meta"]["is_model_result"] is False
    assert data["overall"] == result["overall"]
    assert sorted(p.stem for p in (tmp_path / "out" / "transcripts").iterdir()) == sorted(IDS)
    rendered = render_markdown(data["meta"], data)
    assert rendered == md


def test_source_date_epoch_makes_two_runs_byte_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1791765279")
    result = run_suite(ScriptedProvider(), SUITE, tmp_path / "a", only=set(IDS))
    assert result["meta"]["generated_at"] == "2026-10-12T00:34:39Z"
    run_suite(ScriptedProvider(), SUITE, tmp_path / "b", only=set(IDS))
    for name in ("report.md", "results.json", "transcripts/t1_read_readme.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_cli_run_and_checks(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["check-suite"]) == 0
    assert main(["list-tasks"]) == 0 and "t1_read_readme" in capsys.readouterr().out
    out = tmp_path / "cli"
    assert (
        main(["run", "--provider", "scripted", "--out", str(out), "--only", "t1_calc_power"]) == 0
    )
    assert "1/1 passed" in capsys.readouterr().out and (out / "report.md").exists()
    assert main(["run", "--provider", "anthropic", "--out", str(out)]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_cost_per_success_and_latency_fields():
    good = ScriptedProvider()
    records = [run_task(good, t) for t in SUITE.tasks if t.id in IDS]
    m = compute_metrics(records, SUITE, good.model)
    assert m["overall"]["cost_per_success_usd"] == 0.0  # replay providers cost nothing
    assert m["overall"]["mean_latency_ms"] is None and m["tasks"][0]["latency_ms"] is None
    flawed = ScriptedProvider(flawed=True)
    none_pass = [run_task(flawed, t) for t in SUITE.tasks if t.id == "t3_missing_file"]
    m = compute_metrics(none_pass, SUITE, flawed.model)
    assert m["overall"]["passed"] == 0 and m["overall"]["cost_per_success_usd"] is None
    records[0].latency_ms, records[1].latency_ms = 1000.0, 3000.0
    m = compute_metrics(records, SUITE, "claude-opus-5")
    assert m["overall"]["mean_latency_ms"] == 2000.0
    assert m["overall"]["cost_per_success_usd"] == round(m["overall"]["estimated_cost_usd"] / 3, 6)
    md = render_markdown(
        {
            "provider": "x",
            "model": "claude-opus-5",
            "suite": "s",
            "suite_version": 1,
            "generated_at": "t",
        },
        m,
    )
    assert "per success)" in md and "- Mean latency: 2000 ms/task" in md
    md = render_markdown(
        {
            "provider": "scripted",
            "model": "replay-v1",
            "suite": "s",
            "suite_version": 1,
            "generated_at": "t",
        },
        compute_metrics(records, SUITE, "replay-v1"),
    )
    assert "- Estimated cost: $0.0000 ($0.0000 per success)" in md
    assert "- Mean latency: 2000 ms/task" in md
