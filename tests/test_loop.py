import pytest
from fakes import ListProvider, answer, call

from agent_eval.agent import run_loop
from agent_eval.tools import Sandbox, ToolRegistry
from agent_eval.tools.base import Tool, obj_schema
from agent_eval.types import Budget, Message, ToolCall


def go(provider, budget=None, sandbox=None):
    budget = budget or Budget(max_steps=5, max_tokens=10_000)
    sb = sandbox or Sandbox.fresh()
    rec = run_loop(provider, ToolRegistry(), sb, "do it", budget, task_id="t")
    return rec, sb


def test_happy_path_records_transcript_and_usage():
    p = ListProvider([call("fs_read", path="/docs/readme.txt"), answer("Owner is ops team")])
    rec, _ = go(p)
    assert rec.stop_reason == "answered"
    assert rec.final_answer == "Owner is ops team"
    assert (rec.steps, rec.tool_calls, rec.tool_errors, rec.validation_errors) == (2, 1, 0, 0)
    assert rec.usage.input_tokens == 200 and rec.usage.output_tokens == 20
    assert [e["type"] for e in rec.transcript] == ["assistant", "tool_result", "assistant"]
    assert "Project Atlas" in rec.transcript[1]["content"]
    # the provider saw the tool result on its second call
    second = p.seen[1]
    assert second[-1].role == "tool" and not second[-1].tool_results[0].is_error


def test_state_changes_persist_in_sandbox():
    p = ListProvider([call("fs_write", path="/out.txt", content="x"), answer("done")])
    _, sb = go(p)
    assert sb.fs.read("/out.txt") == "x"


def test_schema_validation_errors_are_returned_not_raised():
    p = ListProvider([call("fs_read", file="/docs/readme.txt"), answer("gave up")])
    rec, _ = go(p)
    result = rec.transcript[1]
    assert result["is_error"] and "unknown key 'file'" in result["content"]
    assert "missing required key 'path'" in result["content"]
    assert rec.validation_errors == 1 and rec.tool_errors == 0


def test_unknown_tool_and_parse_error_count_as_validation_errors():
    bad = Message("assistant", tool_calls=[ToolCall("x", "fs_read", {}, parse_error="bad json")])
    p = ListProvider([call("fs_delete", path="/a"), bad, answer("ok")])
    rec, _ = go(p)
    assert rec.validation_errors == 2
    assert "available: fs_read" in rec.transcript[1]["content"]
    assert "bad json" in rec.transcript[3]["content"]


def test_domain_tool_errors_are_counted_and_loop_continues():
    p = ListProvider(
        [call("tickets_get", id="T-9999"), call("tickets_get", id="T-1001"), answer("ok")]
    )
    rec, _ = go(p)
    assert rec.tool_errors == 1 and rec.tool_calls == 2 and rec.stop_reason == "answered"
    assert rec.transcript[1]["content"] == "error: 404: ticket T-9999 not found"


def test_step_budget_stops_the_loop():
    p = ListProvider([call("fs_list", path="/")] * 10)
    rec, _ = go(p, Budget(max_steps=3, max_tokens=10_000))
    assert rec.stop_reason == "step_budget" and rec.steps == 3 and rec.tool_calls == 3


def test_token_budget_stops_the_loop():
    p = ListProvider([call("fs_list", path="/")] * 10)
    rec, _ = go(p, Budget(max_steps=10, max_tokens=250))
    assert rec.stop_reason == "token_budget" and rec.steps == 3  # 110 per step, 330 > 250


def test_provider_error_and_refusal_and_truncation():
    rec, _ = go(ListProvider([]))
    assert rec.stop_reason == "provider_error" and rec.transcript[0]["type"] == "provider_error"
    rec, _ = go(ListProvider([answer("")], stop_reasons=["refusal"]))
    assert rec.stop_reason == "refusal"
    rec, _ = go(ListProvider([answer("partial")], stop_reasons=["max_tokens"]))
    assert rec.stop_reason == "truncated" and rec.final_answer == "partial"


class _ExplodingProvider:
    """Raises something that is not a ProviderError, like an SDK or conversion bug would."""

    name = "exploding"
    model = "exploding-model"

    def start_task(self, task):
        return None

    def complete(self, messages, tools):
        raise RuntimeError("sdk exploded")


def test_unexpected_provider_exception_is_recorded_not_raised():
    rec, _ = go(_ExplodingProvider())
    assert rec.stop_reason == "provider_error" and rec.steps == 1 and rec.final_answer == ""
    assert rec.transcript[0]["error"] == "unexpected RuntimeError: sdk exploded"


def test_unexpected_tool_exception_is_recorded_not_raised():
    def boom(sb, args):
        raise KeyError("oops")

    reg = ToolRegistry([Tool("boom", "always fails", obj_schema({}, []), boom)])
    p = ListProvider([call("boom"), answer("ok")])
    rec = run_loop(p, reg, Sandbox.fresh(), "q", Budget(), task_id="t")
    assert rec.stop_reason == "answered" and rec.tool_errors == 1 and rec.validation_errors == 0
    result = rec.transcript[1]
    assert result["is_error"] and result["content"] == "internal tool error (KeyError): 'oops'"


def test_context_window_exceeded_counts_as_truncated():
    p = ListProvider([answer("partial")], stop_reasons=["model_context_window_exceeded"])
    rec, _ = go(p)
    assert rec.stop_reason == "truncated" and rec.final_answer == "partial"


def test_registry_subset_limits_available_tools():
    reg = ToolRegistry().subset(["calculator"])
    assert reg.names() == ["calculator"]
    with pytest.raises(KeyError):
        ToolRegistry().subset(["nope"])
    p = ListProvider([call("fs_read", path="/docs/readme.txt"), answer("x")])
    rec = run_loop(p, reg, Sandbox.fresh(), "q", Budget(), task_id="t")
    assert rec.validation_errors == 1 and "unknown tool 'fs_read'" in rec.transcript[1]["content"]


class _TimedProvider(ListProvider):
    """Reports a wall-time latency on every call, as the live providers do."""

    def complete(self, messages, tools):
        resp = super().complete(messages, tools)
        resp.latency_ms = 250.25
        return resp


def test_latency_is_a_placeholder_for_replay_providers_and_summed_for_live_ones():
    rec, _ = go(ListProvider([call("fs_list", path="/"), answer("ok")]))
    assert rec.latency_ms is None
    assert [e["latency_ms"] for e in rec.transcript if e["type"] == "assistant"] == [None, None]
    rec, _ = go(_TimedProvider([call("fs_list", path="/"), answer("ok")]))
    assert rec.latency_ms == 500.5
    assert rec.transcript[0]["latency_ms"] == 250.25


def test_record_carries_its_budget_for_replay():
    rec, _ = go(ListProvider([answer("ok")]), Budget(max_steps=4, max_tokens=999))
    d = rec.to_dict()
    assert d["budget"] == {"max_steps": 4, "max_tokens": 999} and d["latency_ms"] is None
