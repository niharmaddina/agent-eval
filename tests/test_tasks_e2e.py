import pytest

from agent_eval.metrics import failure_category
from agent_eval.providers.scripted import ScriptedProvider
from agent_eval.runner import run_task
from agent_eval.tasks import DEFAULT_SUITE, load_suite
from agent_eval.tools import ToolRegistry
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
