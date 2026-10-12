"""Fake ticketing/CRM API seeded from a JSON fixture."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from agent_eval.tools.base import Tool, ToolError, obj_schema
from agent_eval.tools.sandbox import Sandbox

STATUSES = ["open", "in_progress", "blocked", "resolved", "closed"]
PRIORITIES = ["low", "medium", "high", "urgent"]
FIXTURE = Path(__file__).parent / "fixtures" / "tickets.json"


class TicketStore:
    def __init__(self, tickets: list[dict[str, Any]]) -> None:
        self.tickets: dict[str, dict[str, Any]] = {t["id"]: copy.deepcopy(t) for t in tickets}
        for t in self.tickets.values():
            t.setdefault("notes", [])

    @classmethod
    def from_fixture(cls, path: Path = FIXTURE) -> TicketStore:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["tickets"])

    def get(self, ticket_id: str) -> dict[str, Any]:
        if ticket_id not in self.tickets:
            raise ToolError(f"404: ticket {ticket_id} not found")
        return self.tickets[ticket_id]

    def list(self, status: str | None = None, assignee: str | None = None) -> list[dict[str, Any]]:
        out = []
        for t in self.tickets.values():
            if status and t["status"] != status:
                continue
            if assignee and t["assignee"] != assignee:
                continue
            out.append(t)
        return out

    def update(self, ticket_id: str, **fields: Any) -> dict[str, Any]:
        t = self.get(ticket_id)
        changes = {k: v for k, v in fields.items() if v is not None}
        if not changes:
            raise ToolError("400: no fields to update")
        if t["status"] == "closed" and changes.get("status") != "open":
            raise ToolError(f"409: ticket {ticket_id} is closed; reopen it first")
        t.update(changes)
        return t

    def add_note(self, ticket_id: str, text: str) -> int:
        if not text.strip():
            raise ToolError("400: note text may not be empty")
        notes: list[str] = self.get(ticket_id)["notes"]
        notes.append(text)
        return len(notes)


def _summary(t: dict[str, Any]) -> str:
    return f"{t['id']} [{t['status']}/{t['priority']}] {t['title']} (assignee: {t['assignee']})"


def _list(sb: Sandbox, args: dict[str, Any]) -> str:
    rows = sb.tickets.list(args.get("status"), args.get("assignee"))
    return "\n".join(_summary(t) for t in rows) if rows else "no tickets match"


def _get(sb: Sandbox, args: dict[str, Any]) -> str:
    return json.dumps(sb.tickets.get(args["id"]), indent=1, sort_keys=True)


def _update(sb: Sandbox, args: dict[str, Any]) -> str:
    t = sb.tickets.update(
        args["id"],
        status=args.get("status"),
        assignee=args.get("assignee"),
        priority=args.get("priority"),
    )
    return "updated: " + _summary(t)


def _note(sb: Sandbox, args: dict[str, Any]) -> str:
    n = sb.tickets.add_note(args["id"], args["text"])
    return f"note #{n} added to {args['id']}"


_ID = {"type": "string", "description": "Ticket id such as T-1001"}

TICKET_TOOLS: list[Tool] = [
    Tool(
        "tickets_list",
        "List tickets, optionally filtered by status and/or assignee.",
        obj_schema(
            {"status": {"type": "string", "enum": STATUSES}, "assignee": {"type": "string"}}, []
        ),
        _list,
    ),
    Tool("tickets_get", "Fetch one ticket as JSON by id.", obj_schema({"id": _ID}, ["id"]), _get),
    Tool(
        "tickets_update",
        "Update status, assignee and/or priority of a ticket.",
        obj_schema(
            {
                "id": _ID,
                "status": {"type": "string", "enum": STATUSES},
                "assignee": {"type": "string"},
                "priority": {"type": "string", "enum": PRIORITIES},
            },
            ["id"],
        ),
        _update,
    ),
    Tool(
        "tickets_add_note",
        "Append a free-text note to a ticket.",
        obj_schema({"id": _ID, "text": {"type": "string"}}, ["id", "text"]),
        _note,
    ),
]
