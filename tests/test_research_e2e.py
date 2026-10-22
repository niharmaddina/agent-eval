import pytest

from agent_eval.cli import main
from agent_eval.metrics import compute_metrics, failure_category
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.runner import run_suite, run_task
from agent_eval.tasks import RESEARCH_SUITE, load_suite, run_checks
from agent_eval.tools import Sandbox, ToolRegistry
from agent_eval.tools.schema import validate

SUITE = load_suite(RESEARCH_SUITE)
BY_ID = {t.id: t for t in SUITE.tasks}


def test_suite_shape():
    assert SUITE.name == "research" and len(SUITE.tasks) >= 15
    assert SUITE.tiers == {
        1: "single lookup",
        2: "multi-page",
        3: "error recovery",
        4: "budget pressure",
    }
    assert all(len(SUITE.by_tier(t)) >= 3 for t in SUITE.tiers)
    for task in SUITE.tasks:
        assert task.script_flawed is not None, task.id
        assert task.tools and set(task.tools) & {"web_search", "web_fetch"}, task.id
        assert task.notes, task.id


def test_scripts_outside_tier_three_use_valid_calls():
    reg = ToolRegistry()
    for task in SUITE.tasks:
        if task.tier == 3:
            continue
        for step in task.script:
            if "call" in step:
                tool = reg.get(step["call"]["tool"])
                assert tool is not None and tool.name in (task.tools or []), (task.id, step)
                assert validate(step["call"].get("args", {}), tool.input_schema) == [], task.id


def test_every_task_passes_with_the_scripted_provider():
    for task in SUITE.tasks:
        rec = run_task(ScriptedProvider(), task)
        assert rec.passed and rec.stop_reason == "answered", (task.id, rec.failures)


def test_tier_three_scripts_hit_an_error_and_recover():
    for task in SUITE.by_tier(3):
        rec = run_task(ScriptedProvider(), task)
        assert rec.passed and rec.tool_errors + rec.validation_errors >= 1, task.id
        # the error is never the last tool result: the script recovers or reports a fallback
        assert rec.tool_calls >= 2


def test_tier_four_shortest_path_is_three_calls_under_a_budget_of_five():
    for task in SUITE.by_tier(4):
        assert task.budget.max_steps == 5, task.id
        assert sum("call" in s for s in task.script) == 3, task.id
        rec = run_task(ScriptedProvider(), task)
        assert rec.passed and rec.steps == 4 and rec.tool_calls == 3, task.id


def test_flawed_provider_replays_explicit_scripts_verbatim():
    rec = run_task(ScriptedProvider(flawed=True), BY_ID["r3_dead_link_report"])
    assert not rec.passed and failure_category(rec) == "gave_up_after_error"
    # no generic apology was substituted: the declared script_flawed answer is used as written
    assert rec.final_answer == "I could not complete the task: the 2025 price list returned 404."
    rec = run_task(ScriptedProvider(flawed=True), BY_ID["r1_fetch_owner"])
    assert rec.steps == 1 and rec.tool_calls == 0 and failure_category(rec) == "wrong_answer"


def test_flawed_outcomes_by_tier():
    flawed = ScriptedProvider(flawed=True)
    records = [run_task(flawed, t) for t in SUITE.tasks]
    by_tier = {tier: [r for r in records if BY_ID[r.task_id].tier == tier] for tier in SUITE.tiers}
    assert all(failure_category(r) == "step_budget" for r in by_tier[4])
    assert all(r.steps == 5 and r.final_answer == "" for r in by_tier[4])
    assert all(failure_category(r) == "gave_up_after_error" for r in by_tier[3])
    assert {failure_category(r) for r in by_tier[2]} == {None, "wrong_answer"}
    m = compute_metrics(records, SUITE, flawed.model)
    assert m["overall"]["passed"] == 5 and m["overall"]["total"] == len(SUITE.tasks)
    assert m["failures"] == {"gave_up_after_error": 4, "step_budget": 3, "wrong_answer": 5}
    assert [t["label"] for t in m["tiers"]] == list(SUITE.tiers.values())


def test_conflict_tasks_require_both_sources_to_be_cited():
    task = BY_ID["r2_reconcile_price"]
    urls = ["https://news.example/tools/atlas-review", "https://atlas.example/pricing"]
    assert all(any(u in str(c.get("answer_contains", [])) for c in task.checks) for u in urls)
    one_source = "The Team plan is $35 per seat, see https://news.example/tools/atlas-review; $40."
    failures = run_checks(task.checks, Sandbox.fresh(), one_source)
    assert len(failures) == 1 and "https://atlas.example/pricing" in failures[0]
    both = f"{urls[0]} says $35; {urls[1]} says $40 and is current."
    assert run_checks(task.checks, Sandbox.fresh(), both) == []
    # the retry-limit pair needs both figures as whole numbers: the wiki's 2025 edit date must
    # not stand in for the "5", so an answer claiming the two sources agree fails
    agree = (
        "Both say 8 attempts (https://atlas.example/docs/limits; https://wiki.example/atlas, "
        "last edited 2025-11-02)."
    )
    both = (
        "Wiki (https://wiki.example/atlas): 5 attempts; official page "
        "(https://atlas.example/docs/limits): 8 attempts, raised in 1.2.0."
    )
    for tid in ("r2_reconcile_retries", "r4_two_sources_retries"):
        failures = run_checks(BY_ID[tid].checks, Sandbox.fresh(), agree)
        assert len(failures) == 1 and "/\\b5\\b/" in failures[0], (tid, failures)
        assert run_checks(BY_ID[tid].checks, Sandbox.fresh(), both) == [], tid


def test_link_chain_accepts_the_figure_on_either_side_of_the_word():
    checks = BY_ID["r2_link_chain"].checks
    for ok in (
        "Default deploy retries: 3.",
        "Atlas defaults to 3 deploy retries.",
        "retry count: 3",
    ):
        assert run_checks(checks, Sandbox.fresh(), ok) == [], ok
    for bad in (
        "Atlas retries a deployment 5 times by default.",
        "Python 3.11; retries default 30.",
    ):
        assert run_checks(checks, Sandbox.fresh(), bad), bad


def test_cli_check_and_list_show_suite_tiers(capsys):
    assert main(["check-suite", "--suite", str(RESEARCH_SUITE)]) == 0
    assert "17 tasks, tiers 1=single lookup" in capsys.readouterr().out
    assert main(["list-tasks", "--suite", str(RESEARCH_SUITE)]) == 0
    out = capsys.readouterr().out
    assert "r4_incident_chain\ttier 4 (budget pressure)" in out
    assert (
        main(["run", "--provider", "scripted", "--suite", str(RESEARCH_SUITE), "--tier", "9"]) == 2
    )
    assert "tier 9 not in [1, 2, 3, 4]" in capsys.readouterr().err


def test_cli_default_output_is_per_suite_and_provider(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    args = [
        "run",
        "--provider",
        "scripted",
        "--suite",
        str(RESEARCH_SUITE),
        "--only",
        "r1_fetch_owner",
    ]
    assert main(args) == 0
    assert (tmp_path / "results" / "research" / "scripted" / "report.md").exists()
    assert "1/1 passed" in capsys.readouterr().out


def test_two_suites_do_not_share_tier_labels(tmp_path):
    basic = run_suite(ScriptedProvider(), load_suite(), tmp_path / "b", only={"t1_read_readme"})
    research = run_suite(ScriptedProvider(), SUITE, tmp_path / "r", only={"r1_fetch_owner"})
    assert basic["tiers"][0]["label"] == "single tool"
    assert research["tiers"][0]["label"] == "single lookup"


_SUITE = """
suite: probe
{tiers}
tasks:
  - id: a
    tier: {tier}
    prompt: p
    check:
      - answer_contains: x
    script:
      - answer: x
{flawed}
"""


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"tiers": "tiers: {1: one}", "tier": 2}, "tier must be one of \\[1\\]"),
        ({"tiers": "tiers: {one: 1}", "tier": 1}, "expected integer -> string"),
        ({"tiers": "tiers: []", "tier": 1}, "non-empty mapping"),
        ({"flawed": "    script_flawed: []"}, "non-empty list"),
        ({"flawed": "    script_flawed:\n      - call: {args: {}}"}, "script_flawed call needs"),
        ({"flawed": "    script_flawed:\n      - {call: {tool: x}, answer: y}"}, "exactly one"),
    ],
)
def test_suite_tiers_and_flawed_scripts_are_validated(tmp_path, kwargs, message):
    params = {"tiers": "", "tier": 1, "flawed": ""} | kwargs
    path = tmp_path / "s.yaml"
    path.write_text(_SUITE.format(**params), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_suite(path)


def test_suite_level_tools_apply_to_tasks_without_their_own(tmp_path):
    basic = load_suite()
    assert all(t.tools == basic.tasks[0].tools for t in basic.tasks)
    assert basic.tasks[0].tools is not None and "web_fetch" not in basic.tasks[0].tools
    text = _SUITE.format(tiers="tools: [calculator]", tier=1, flawed="    tools: [fs_read]")
    path = tmp_path / "s.yaml"
    path.write_text(text, encoding="utf-8")
    assert load_suite(path).tasks[0].tools == ["fs_read"]  # a task's own list wins
    path.write_text(_SUITE.format(tiers="tools: [calculator]", tier=1, flawed=""))
    assert load_suite(path).tasks[0].tools == ["calculator"]
    path.write_text(_SUITE.format(tiers="tools: [fs_nuke]", tier=1, flawed=""))
    with pytest.raises(ValueError, match="suite: unknown tools"):
        load_suite(path)


def test_suite_without_tiers_mapping_uses_defaults(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(_SUITE.format(tiers="", tier=3, flawed=""), encoding="utf-8")
    suite = load_suite(path)
    assert suite.tiers == {1: "single tool", 2: "multi-step", 3: "error recovery"}
    assert suite.tasks[0].script_flawed is None
