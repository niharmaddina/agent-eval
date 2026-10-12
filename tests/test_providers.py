import json

import pytest

from agent_eval.providers import get_provider
from agent_eval.providers.anthropic_provider import to_anthropic
from agent_eval.providers.base import ProviderError, ProviderUnavailable
from agent_eval.providers.openai_compat import to_openai
from agent_eval.providers.scripted import flawed_script, render_answer
from agent_eval.tools import ToolRegistry
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


def _mock_client(sdk_client_cls, httpx, responses):
    """Build an SDK client whose transport replays canned responses and records request bodies."""
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        status, body = responses[len(seen) - 1]
        return httpx.Response(status, json=body)

    client = sdk_client_cls(
        api_key="sk-test-not-a-real-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    return client, seen


def test_anthropic_provider_round_trip_offline(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")
    from agent_eval.providers.anthropic_provider import AnthropicProvider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    tool_use_reply = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5",
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": "Reading."},
            {"type": "tool_use", "id": "toolu_1", "name": "fs_read", "input": {"path": "/a"}},
        ],
        "usage": {"input_tokens": 321, "output_tokens": 45},
    }
    final_reply = dict(
        tool_use_reply, stop_reason="end_turn", content=[{"type": "text", "text": "ok"}]
    )
    rate_limited = {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}
    client, seen = _mock_client(
        anthropic.Anthropic, httpx, [(200, tool_use_reply), (200, final_reply), (429, rate_limited)]
    )
    provider = AnthropicProvider(model="claude-opus-5", client=client)
    specs = ToolRegistry().subset(["fs_read"]).specs()

    resp = provider.complete(CONVO, specs)
    body = seen[0]
    assert body["model"] == "claude-opus-5" and body["system"] == "sys"
    assert body["max_tokens"] == 16_000
    assert body["tools"] == [
        {
            "name": "fs_read",
            "description": specs[0]["description"],
            "input_schema": specs[0]["input_schema"],
        }
    ]
    assert body["messages"][1]["content"][1] == {
        "type": "tool_use",
        "id": "c1",
        "name": "fs_read",
        "input": {"path": "/a"},
    }
    assert body["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "c1", "content": "error: missing", "is_error": True}
    ]
    assert resp.stop_reason == "tool_use" and resp.message.content == "Reading."
    assert [(c.id, c.name, c.arguments) for c in resp.message.tool_calls] == [
        ("toolu_1", "fs_read", {"path": "/a"})
    ]
    assert (resp.usage.input_tokens, resp.usage.output_tokens, resp.usage.estimated) == (
        321,
        45,
        False,
    )

    # The next turn echoes the native blocks (thinking included) and sends the result back.
    follow_up = [*CONVO, resp.message, Message("tool", tool_results=[ToolResult("toolu_1", "hi")])]
    resp2 = provider.complete(follow_up, specs)
    echoed = seen[1]["messages"][3]["content"]
    assert [b["type"] for b in echoed] == ["thinking", "text", "tool_use"]
    assert echoed[0]["signature"] == "sig" and echoed[2]["id"] == "toolu_1"
    assert seen[1]["messages"][4]["content"][0]["tool_use_id"] == "toolu_1"
    assert resp2.stop_reason == "end_turn" and resp2.message.content == "ok"

    with pytest.raises(ProviderError, match="HTTP 429"):
        provider.complete(CONVO, specs)


def test_openai_compat_provider_round_trip_offline(monkeypatch):
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx2")
    from agent_eval.providers.openai_compat import OpenAICompatProvider

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    reply = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "some-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "fs_read", "arguments": '{"path": "/a"}'},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "fs_read", "arguments": "{not json"},
                        },
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }
    server_error = {"error": {"message": "boom", "type": "server_error"}}
    client, seen = _mock_client(openai.OpenAI, httpx, [(200, reply), (500, server_error)])
    provider = OpenAICompatProvider(model="some-model", client=client)
    specs = ToolRegistry().subset(["fs_read"]).specs()

    resp = provider.complete(CONVO, specs)
    body = seen[0]
    assert body["model"] == "some-model"
    assert body["tools"][0]["type"] == "function"
    assert body["tools"][0]["function"]["parameters"] == specs[0]["input_schema"]
    assert body["messages"][3] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "error: missing",
    }
    assert resp.stop_reason == "tool_calls"
    good, bad = resp.message.tool_calls
    assert (good.id, good.arguments, good.parse_error) == ("call_1", {"path": "/a"}, None)
    assert bad.arguments == {} and bad.parse_error and "non-JSON" in bad.parse_error
    assert (resp.usage.input_tokens, resp.usage.output_tokens, resp.usage.estimated) == (
        100,
        20,
        False,
    )

    with pytest.raises(ProviderError, match="openai_compat"):
        provider.complete(CONVO, specs)


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
