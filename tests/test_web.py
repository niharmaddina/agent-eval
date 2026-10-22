import json

import pytest

from agent_eval.tools import Sandbox, ToolError, ToolRegistry
from agent_eval.tools.schema import validate
from agent_eval.tools.web import FIXTURE, Page, WebStore, tokenize


@pytest.fixture
def sb() -> Sandbox:
    return Sandbox.fresh()


def run(sb: Sandbox, name: str, **args):
    tool = ToolRegistry().get(name)
    assert tool is not None
    assert validate(args, tool.input_schema) == []
    return tool.execute(sb, args)


def test_fixture_shape_and_links_resolve():
    data = json.loads(FIXTURE.read_text())
    pages = {p["url"] for p in data["pages"]}
    errors = {e["url"]: e["kind"] for e in data["errors"]}
    assert len(pages) >= 12 and set(errors.values()) == {"404", "timeout"}
    assert not pages & errors.keys()
    for page in data["pages"]:
        for link in page["links"]:
            assert link in pages or link in errors, (page["url"], link)
        assert page["links"], page["url"]  # every page links somewhere, so chains exist
    # the error URLs are reachable from a real page, so link-following can hit them
    linked = {link for p in data["pages"] for link in p["links"]}
    assert errors.keys() <= linked


def test_tokenize_drops_stopwords_and_short_tokens():
    assert tokenize("Does Atlas run on Windows?") == {"atlas", "run", "windows"}
    assert tokenize("the of and a") == set()
    assert tokenize("3.11 or newer") == {"11", "newer"}


def test_search_ranks_title_matches_above_body_matches(sb):
    out = run(sb, "web_search", query="Atlas pricing")
    lines = out.splitlines()
    assert lines[0] == "5 results for 'Atlas pricing':"
    assert lines[1] == "1. https://atlas.example/pricing - Atlas pricing"
    assert lines[2].startswith("   ") and "pricing" in lines[2].lower()  # snippet names a term
    assert "https://atlas.example/pricing/2025" in out  # stale index entries are searchable
    assert (
        run(sb, "web_search", query="Atlas rate limits quotas")
        .splitlines()[1]
        .endswith("https://atlas.example/docs/limits - Atlas rate limits and quotas")
    )


def test_search_no_results_and_result_cap(sb):
    assert run(sb, "web_search", query="zzz qqq") == "no results for 'zzz qqq'"
    assert run(sb, "web_search", query="the of") == "no results for 'the of'"
    assert run(sb, "web_search", query="Atlas").count("\n") == 10  # 5 hits, two lines each


def test_search_ties_break_on_url_for_determinism():
    store = WebStore(
        {
            "https://b.example/x": Page("https://b.example/x", "Same title", "same body"),
            "https://a.example/x": Page("https://a.example/x", "Same title", "same body"),
        }
    )
    assert [p.url for _, p in store.search("same title")] == [
        "https://a.example/x",
        "https://b.example/x",
    ]
    assert store.search("") == []


def test_fetch_renders_title_body_and_links(sb):
    out = run(sb, "web_fetch", url="https://atlas.example/")
    assert out.startswith("# Atlas - internal deployment tool\nhttps://atlas.example/\n\n")
    assert "owned and maintained by the ops team" in out
    assert "Links:\n- https://atlas.example/docs\n" in out
    # a trailing slash is not a different page, in either direction
    assert run(sb, "web_fetch", url="https://atlas.example/docs/") == run(
        sb, "web_fetch", url="https://atlas.example/docs"
    )
    assert run(sb, "web_fetch", url="https://atlas.example") == run(
        sb, "web_fetch", url="https://atlas.example/"
    )
    with pytest.raises(ToolError, match="404 Not Found"):
        sb.web.fetch("https://atlas.example/docs//")  # only one slash is forgiven


def test_fetch_errors_are_deterministic_and_logged(sb):
    with pytest.raises(ToolError, match=r"404 Not Found.*removed"):
        sb.web.fetch("https://atlas.example/pricing/2025")
    with pytest.raises(ToolError, match="timeout"):
        sb.web.fetch("https://mirror.example/atlas/docs/limits")
    with pytest.raises(ToolError, match="404 Not Found"):
        sb.web.fetch("https://atlas.example/nope")
    with pytest.raises(ToolError, match="https://"):
        sb.web.fetch("atlas.example/docs")
    assert sb.web.fetched == [
        "https://atlas.example/pricing/2025",
        "https://mirror.example/atlas/docs/limits",
        "https://atlas.example/nope",
        "atlas.example/docs",
    ]
    assert Sandbox.fresh().web.fetched == []  # a fresh sandbox has a fresh log


def test_fixture_rejects_unknown_error_kind(tmp_path):
    bad = tmp_path / "web.json"
    bad.write_text(json.dumps({"pages": [], "errors": [{"url": "https://x", "kind": "500"}]}))
    with pytest.raises(ValueError, match="unknown error kind"):
        WebStore.from_fixture(bad)


def test_web_tools_are_in_the_registry_with_closed_schemas():
    reg = ToolRegistry()
    for name in ("web_search", "web_fetch"):
        tool = reg.get(name)
        assert tool is not None and tool.input_schema["additionalProperties"] is False
    assert validate({"link": "x"}, reg.get("web_fetch").input_schema) == [
        "$: missing required key 'url'",
        "$: unknown key 'link'",
    ]
