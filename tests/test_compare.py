import json

import pytest

from agent_eval.cli import main
from agent_eval.compare import compare, load_results, render_markdown, write_compare
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.runner import run_suite
from agent_eval.tasks import RESEARCH_SUITE, load_suite

SUITE = load_suite(RESEARCH_SUITE)
IDS = {
    "r1_fetch_owner",
    "r1_fetch_uptime",
    "r2_reconcile_price",
    "r3_timeout_mirror",
    "r4_price_gap",
}


@pytest.fixture(scope="module")
def dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("cmp")
    run_suite(ScriptedProvider(), SUITE, root / "a", only=IDS)
    run_suite(ScriptedProvider(flawed=True), SUITE, root / "b", only=IDS)
    return root / "a", root / "b"


def test_compare_classifies_tasks_and_sums_deltas(dirs):
    a, b = dirs
    cmp = compare(load_results(a), load_results(b))
    s = cmp["summary"]
    assert (s["common_tasks"], s["passed_a"], s["passed_b"], s["passed_delta"]) == (5, 5, 1, -4)
    assert (s["newly_failing"], s["newly_passing"], s["pass_both"], s["fail_both"]) == (4, 0, 1, 0)
    rows = {r["task_id"]: r for r in cmp["tasks"]}
    assert rows["r1_fetch_uptime"]["status"] == "pass_both"
    owner = rows["r1_fetch_owner"]
    assert owner["status"] == "newly_failing" and owner["steps_delta"] == -1
    assert owner["tokens_delta"] == owner["tokens_b"] - owner["tokens_a"] < 0
    budget = rows["r4_price_gap"]
    assert budget["stop_b"] == "step_budget" and budget["steps_delta"] == 1
    assert s["steps_delta"] == sum(r["steps_delta"] for r in cmp["tasks"])
    assert s["tokens_delta"] == sum(r["tokens_delta"] for r in cmp["tasks"])
    tiers = {t["tier"]: t for t in cmp["tiers"]}
    assert [t["label"] for t in cmp["tiers"]] == list(SUITE.tiers.values())
    assert (tiers[1]["passed_a"], tiers[1]["passed_b"], tiers[1]["newly_failing"]) == (2, 1, 1)
    assert tiers[4]["mean_steps_a"] == 4.0 and tiers[4]["mean_steps_b"] == 5.0
    assert s["cost_a"] == 0.0 and s["cost_b"] == 0.0


def test_compare_is_directional(dirs):
    a, b = dirs
    cmp = compare(load_results(b), load_results(a))
    assert cmp["summary"]["newly_passing"] == 4 and cmp["summary"]["newly_failing"] == 0
    assert cmp["summary"]["passed_delta"] == 4 and cmp["summary"]["steps_delta"] > 0


def test_compare_handles_tasks_present_on_one_side_only(dirs, tmp_path):
    a, _ = dirs
    data = load_results(a)
    partial = {**data, "tasks": [t for t in data["tasks"] if t["task_id"] != "r1_fetch_owner"]}
    extra = {**data, "tasks": [*data["tasks"], {**data["tasks"][0], "task_id": "zzz_new"}]}
    cmp = compare(partial, extra)
    statuses = {r["task_id"]: r["status"] for r in cmp["tasks"]}
    assert statuses["r1_fetch_owner"] == "only_in_b" and statuses["zzz_new"] == "only_in_b"
    assert cmp["summary"]["only_in_b"] == 2 and cmp["summary"]["common_tasks"] == 4
    assert "2 only in B" in render_markdown(cmp)


def test_compare_refuses_different_suites(dirs):
    a, _ = dirs
    data = load_results(a)
    other = {**data, "meta": {**data["meta"], "suite": "basic"}}
    with pytest.raises(ValueError, match="suites differ"):
        compare(data, other)
    with pytest.raises(ValueError, match=r"not an agent-eval results\.json"):
        bad = a / "transcripts" / "r1_fetch_owner.json"
        load_results(bad)


def test_markdown_and_json_outputs(dirs, tmp_path):
    a, b = dirs
    cmp = compare(load_results(a), load_results(b))
    md = render_markdown(cmp)
    assert md.startswith(
        "# agent-eval compare: A = `scripted` (replay-v1) -> B = `scripted_flawed`"
    )
    assert (
        "- Passed: 5 -> 1 (-4); newly passing 0, newly failing 4, unchanged 1 pass / 0 fail" in md
    )
    assert "| 4 | budget pressure | 1 | 1 | 0 | -1 | 0 | 1 | 4.0 | 5.0 |" in md
    assert "## Newly failing (4)" in md and "## Newly passing (0)\n\nNone." in md
    assert "| `r4_price_gap` | 4 | 4 -> 5 (+1) |" in md and "## All tasks" not in md
    json_path, md_path = write_compare(tmp_path / "out", cmp)
    assert json.loads(json_path.read_text())["summary"] == cmp["summary"]
    full = md_path.read_text()
    assert "## All tasks" in full and "| `r1_fetch_uptime` | 1 | pass_both |" in full
    # a pipe inside a failure detail (a regex alternation) is escaped, not rewritten, in the cell
    cmp["tasks"][0]["detail_b"] = "answer: does not match /a|b/ in 'x'"
    assert "does not match /a\\|b/ in 'x' |" in render_markdown(cmp)


def test_cli_compare(dirs, tmp_path, capsys):
    a, b = dirs
    assert main(["compare", str(a), str(b)]) == 0
    assert "# agent-eval compare" in capsys.readouterr().out
    assert main(["compare", str(a / "results.json"), str(b), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["newly_failing"] == 4
    assert main(["compare", str(a), str(b), "--out", str(tmp_path / "c")]) == 0
    out = capsys.readouterr().out
    assert "passed 5 -> 1, newly passing 0, newly failing 4" in out
    assert (tmp_path / "c" / "compare.md").exists() and (tmp_path / "c" / "compare.json").exists()
    assert main(["compare", str(a), str(tmp_path / "missing")]) == 2
    assert "compare error" in capsys.readouterr().err
