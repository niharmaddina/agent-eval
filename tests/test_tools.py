import pytest

from agent_eval.tools import ALL_TOOLS, Sandbox, ToolError, ToolRegistry
from agent_eval.tools.calculator import evaluate
from agent_eval.tools.filesystem import InMemoryFS
from agent_eval.tools.schema import validate
from agent_eval.tools.tickets import TicketStore


@pytest.fixture
def sb() -> Sandbox:
    return Sandbox.fresh()


def run(sb: Sandbox, name: str, **args):
    tool = ToolRegistry().get(name)
    assert tool is not None
    assert validate(args, tool.input_schema) == []
    return tool.execute(sb, args)


# --- file system -------------------------------------------------------------------------
def test_fs_read_write_roundtrip(sb):
    assert "Owner: ops team" in run(sb, "fs_read", path="/docs/readme.txt")
    assert run(sb, "fs_write", path="/x/y.txt", content="hi") == "wrote 2 characters to /x/y.txt"
    assert run(sb, "fs_read", path="/x/y.txt") == "hi"


def test_fs_list_marks_directories_and_sorts(sb):
    assert run(sb, "fs_list", path="/").splitlines() == ["config/", "data/", "docs/", "notes/"]
    assert run(sb, "fs_list", path="/data") == "sales_q1.csv\nsales_q2.csv"
    assert run(sb, "fs_list").startswith("config/")


def test_fs_search_is_case_insensitive_and_scoped(sb):
    assert run(sb, "fs_search", query="LOGIN BUG") == "/docs/changelog.md"
    assert (
        run(sb, "fs_search", query="north", path="/data")
        == "/data/sales_q1.csv\n/data/sales_q2.csv"
    )
    assert run(sb, "fs_search", query="zzz") == "no matches"


def test_fs_errors():
    fs = InMemoryFS({"/a/b.txt": "x"})
    with pytest.raises(ToolError, match="file not found"):
        fs.read("/a/c.txt")
    with pytest.raises(ToolError, match="is a directory"):
        fs.read("/a")
    with pytest.raises(ToolError, match="is a file"):
        fs.listdir("/a/b.txt")
    with pytest.raises(ToolError, match="directory not found"):
        fs.listdir("/nope")
    with pytest.raises(ToolError, match="absolute"):
        fs.read("a/b.txt")
    with pytest.raises(ToolError, match=r"\.\."):
        fs.read("/a/../b.txt")
    with pytest.raises(ToolError, match="is a directory"):
        fs.write("/a", "x")
    with pytest.raises(ToolError, match=r"/a/b\.txt is a file, not a directory"):
        fs.write("/a/b.txt/c.txt", "x")
    assert fs.listdir("/a") == ["b.txt"]  # the refused write left no trace


def test_sandbox_is_fresh_per_instance():
    a, b = Sandbox.fresh(), Sandbox.fresh({"/extra.txt": "1"})
    a.fs.write("/docs/readme.txt", "changed")
    assert "Project Atlas" in b.fs.read("/docs/readme.txt")
    assert b.fs.read("/extra.txt") == "1"


# --- calculator --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("1200 + 850 + 430", "2480"),
        ("2**10 + 7*6", "1066"),
        ("7 // 2", "3"),
        ("7 % 3", "1"),
        ("-(3 - 5)", "2"),
        ("2480 * 0.175", "434"),
        ("10 / 4", "2.5"),
        ("max(1, 9, 3)", "9"),
        ("round(2.567, 2)", "2.57"),
        ("abs(-4)", "4"),
    ],
)
def test_calculator_values(sb, expr, expected):
    assert run(sb, "calculator", expression=expr) == expected


@pytest.mark.parametrize(
    ("expr", "msg"),
    [
        ("1/0", "division by zero"),
        ("__import__('os')", "unsupported syntax"),
        ("2 +", "invalid expression"),
        ("2 ** 100", "exponent too large"),
        ("x + 1", "unsupported"),
        ("round(1.5, ndigits=0)", "keyword"),
        ("1e300 ** 2", "result too large"),
        ("-(1e300 ** 2)", "result too large"),
        ("min()", "invalid call"),
        ("abs(1, 2)", "invalid call"),
        ("round(1.5, 2, 3)", "invalid call"),
    ],
)
def test_calculator_rejects(expr, msg):
    with pytest.raises(ToolError, match=msg):
        evaluate(expr)


# --- tickets -----------------------------------------------------------------------------
def test_tickets_list_filters(sb):
    out = run(sb, "tickets_list", status="open")
    assert out.count("\n") == 2 and "T-1007" in out and "T-1002" not in out
    assert "T-1001" in run(sb, "tickets_list", assignee="dana")
    assert run(sb, "tickets_list", status="blocked", assignee="dana") == "no tickets match"


def test_tickets_get_update_note(sb):
    assert '"priority": "urgent"' in run(sb, "tickets_get", id="T-1003")
    assert run(sb, "tickets_update", id="T-1007", priority="medium", assignee="lee").startswith(
        "updated: T-1007 [open/medium]"
    )
    assert run(sb, "tickets_add_note", id="T-1007", text="hello") == "note #1 added to T-1007"
    assert sb.tickets.get("T-1007")["notes"] == ["hello"]


def test_tickets_errors():
    store = TicketStore.from_fixture()
    with pytest.raises(ToolError, match="404"):
        store.get("T-9999")
    with pytest.raises(ToolError, match="409"):
        store.update("T-1006", status="resolved")
    store.update("T-1006", status="open")  # reopen, then the update is allowed
    assert store.update("T-1006", status="resolved")["status"] == "resolved"
    with pytest.raises(ToolError, match="400: no fields"):
        store.update("T-1001")
    with pytest.raises(ToolError, match="empty"):
        store.add_note("T-1001", "   ")


def test_every_tool_declares_a_closed_object_schema():
    for tool in ALL_TOOLS:
        spec = tool.spec()
        assert spec["input_schema"]["type"] == "object"
        assert spec["input_schema"]["additionalProperties"] is False
        assert spec["description"]
