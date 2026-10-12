import pytest

from agent_eval.providers import get_provider
from agent_eval.providers.anthropic_provider import to_anthropic
from agent_eval.providers.base import ProviderUnavailable
from agent_eval.providers.openai_compat import to_openai
from agent_eval.providers.scripted import flawed_script, render_answer
from agent_eval.types import Message, ToolCall, ToolResult

CONVO = [
    Message("system", "sys"),
    Message("user", "hi"),
    Message("assistant", "looking", tool_calls=[ToolCall("c1", "fs_read", {"path": "/a"})]),
    Message("tool", tool_results=[ToolResult("c1", "error: missing", is_error=True)]),
]


def test_render_answer_placeholders():
    results = [ToolResult("1", "A"), ToolResult("2", "bad", is_error=True), ToolResult("3", "C")]
    assert render_answer("{r0}/{r1}/{last}/{r5}", results) == "A/C/C/unknown"
    assert render_answer("{last}", []) == "unknown"
    assert render_answer("literal {braces} stay", results) == "literal {braces} stay"


def test_flawed_script_drops_last_call_before_answer_only_for_long_scripts():
    short = [{"call": {"tool": "a"}}, {"call": {"tool": "b"}}, {"answer": "x"}]
    assert flawed_script(short) == short
    long = [
        {"call": {"tool": "a"}},
        {"call": {"tool": "b"}},
        {"call": {"tool": "c"}},
        {"answer": "x"},
    ]
    assert flawed_script(long) == [
        {"call": {"tool": "a"}},
        {"call": {"tool": "b"}},
        {"answer": "x"},
    ]


def test_to_anthropic_shapes():
    system, msgs = to_anthropic(CONVO)
    assert system == "sys"
    assert msgs[0] == {"role": "user", "content": "hi"}
    assert msgs[1]["content"] == [
        {"type": "text", "text": "looking"},
        {"type": "tool_use", "id": "c1", "name": "fs_read", "input": {"path": "/a"}},
    ]
    assert msgs[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "c1",
                "content": "error: missing",
                "is_error": True,
            }
        ],
    }
    raw = [Message("assistant", "x", raw=[{"type": "thinking", "thinking": "", "signature": "s"}])]
    assert to_anthropic(raw)[1][0]["content"][0]["type"] == "thinking"


def test_to_openai_shapes():
    msgs = to_openai(CONVO)
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[2]["tool_calls"][0]["function"] == {
        "name": "fs_read",
        "arguments": '{"path": "/a"}',
    }
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": "error: missing"}


def test_real_providers_are_disabled_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailable, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic")
    with pytest.raises(ProviderUnavailable, match="OPENAI_API_KEY"):
        get_provider("openai_compat")
    with pytest.raises(ProviderUnavailable, match="unknown provider"):
        get_provider("gpt-oracle")
    assert get_provider("scripted").name == "scripted"
    assert get_provider("scripted_flawed").name == "scripted_flawed"
