import pytest

from agent_eval.cli import main
from agent_eval.metrics import failure_category
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.runner import run_task
from agent_eval.tasks import DEFAULT_SUITE, load_suite, run_checks
from agent_eval.tools import Sandbox, ToolRegistry
from agent_eval.tools.schema import validate

SUITE = load_suite(DEFAULT_SUITE)
BY_ID = {t.id: t for t in SUITE.tasks}


def test_suite_shape():
    assert SUITE.name == "basic" and len(SUITE.tasks) >= 24
    assert all(len(SUITE.by_tier(t)) >= 8 for t in (1, 2, 3))
    assert len({t.id for t in SUITE.tasks}) == len(SUITE.tasks)


def test_tier_one_and_two_scripts_use_valid_tool_calls():
    reg = ToolRegistry()
    for task in SUITE.tasks:
        if task.tier == 3:
            continue
        for step in task.script:
            if "call" in step:
                tool = reg.get(step["call"]["tool"])
                assert tool is not None, (task.id, step)
                assert validate(step["call"].get("args", {}), tool.input_schema) == [], task.id


@pytest.mark.parametrize("task_id", ["t1_write_hello", "t2_q1_vs_q2", "t3_ticket_404"])
def test_three_tasks_end_to_end_with_scripted_provider(task_id):
    rec = run_task(ScriptedProvider(), BY_ID[task_id])
    assert rec.passed, rec.failures
    assert rec.stop_reason == "answered"


def test_recovery_task_records_the_error_and_the_recovery():
    rec = run_task(ScriptedProvider(), BY_ID["t3_ticket_404"])
    assert rec.tool_errors == 1 and rec.tool_calls == 3 and rec.steps == 4
    assert "T-1004" in rec.final_answer


def test_flawed_provider_gives_up_after_errors_and_skips_steps():
    rec = run_task(ScriptedProvider(flawed=True), BY_ID["t3_missing_file"])
    assert not rec.passed and failure_category(rec) == "gave_up_after_error"
    rec = run_task(ScriptedProvider(flawed=True), BY_ID["t2_summary_file"])
    assert not rec.passed and failure_category(rec) == "wrong_state"
    rec = run_task(ScriptedProvider(flawed=True), BY_ID["t2_sum_q1"])
    assert rec.passed  # two-call scripts are not shortened


def test_every_tier_three_task_exercises_an_error_path():
    for task in SUITE.by_tier(3):
        rec = run_task(ScriptedProvider(), task)
        assert rec.passed, (task.id, rec.failures)
        assert rec.tool_errors + rec.validation_errors >= 1, task.id


_TASK = """
suite: probe
tasks:
  - id: a
    tier: 1
    prompt: p
{extra}
    check:
{check}
    script:
{script}
"""


def _suite(tmp_path, check="      - answer_contains: x", script="      - answer: x", extra=""):
    path = tmp_path / "s.yaml"
    path.write_text(_TASK.format(check=check, script=script, extra=extra), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"extra": "    tools: [fs_read, fs_nuke]"}, "unknown tools \\['fs_nuke'\\]"),
        ({"check": "      - answer_matches: '(unclosed'"}, "invalid regex"),
        ({"check": "      - answer_matches: [a, b]"}, "single regex string"),
        ({"check": "      - file_equals: {path: /x}"}, "missing keys \\['content'\\]"),
        ({"check": "      - file_equals: /x"}, "expected a mapping"),
        ({"check": "      - looks_right: yes"}, "unknown check kind"),
        ({"check": "      []"}, "at least one check"),
        ({"script": "      - call: {args: {path: /x}}"}, "needs 'tool'"),
        ({"script": "      - call: {tool: fs_read, args: nope}"}, "mapping 'args'"),
        ({"script": "      - {call: {tool: fs_read}, answer: x}"}, "exactly one of call/answer"),
    ],
)
def test_check_suite_rejects_malformed_tasks(tmp_path, kwargs, message):
    path = _suite(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=message):
        load_suite(path)
    assert main(["check-suite", "--suite", str(path)]) == 2


def test_cli_rejects_unparseable_yaml(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("tasks: [unclosed", encoding="utf-8")
    assert main(["check-suite", "--suite", str(path)]) == 2
    assert "suite error" in capsys.readouterr().err


def test_malformed_checks_fail_the_task_instead_of_raising():
    sb = Sandbox.fresh()
    failures = run_checks(
        [{"answer_matches": "(unclosed"}, {"file_equals": "/x"}, {"ticket_field": {"id": 1}}],
        sb,
        "answer",
    )
    assert len(failures) == 3 and all(f.startswith("checker:") for f in failures)
    assert "invalid regex" in failures[0]


def test_script_that_never_answers_fails_closed(tmp_path):
    script = "      - call: {tool: fs_read, args: {path: /docs/readme.txt}}"
    task = load_suite(_suite(tmp_path, check="      - answer_contains: ops", script=script)).tasks[
        0
    ]
    rec = run_task(ScriptedProvider(), task)
    assert rec.stop_reason == "answered" and rec.final_answer == "Done." and not rec.passed
    task.budget.max_steps = 1
    rec = run_task(ScriptedProvider(), task)
    assert rec.stop_reason == "step_budget" and rec.final_answer == "" and not rec.passed
    assert failure_category(rec) == "step_budget"
