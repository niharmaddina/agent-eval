"""Per-run sandbox state: a fresh file system and ticket store for every task attempt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_eval.tools.filesystem import InMemoryFS
    from agent_eval.tools.tickets import TicketStore

SEED_FILES: dict[str, str] = {
    "/docs/readme.txt": "Project Atlas\nInternal notes for the Atlas rollout.\nOwner: ops team\n",
    "/docs/changelog.md": (
        "# Changelog\n\n## 1.2.0\n- Added export\n\n## 1.1.0\n- Fixed login bug\n"
    ),
    "/data/sales_q1.csv": "region,amount\nnorth,1200\nsouth,850\neast,430\n",
    "/data/sales_q2.csv": "region,amount\nnorth,1500\nsouth,900\neast,610\n",
    "/notes/todo.txt": "- renew certificates\n- rotate API keys\n- archive old tickets\n",
    "/config/app.json": '{"env": "staging", "retries": 3, "timeout_s": 30}\n',
}


@dataclass
class Sandbox:
    fs: InMemoryFS
    tickets: TicketStore

    @classmethod
    def fresh(
        cls, extra_files: dict[str, str] | None = None, fixture: Path | None = None
    ) -> Sandbox:
        from agent_eval.tools.filesystem import InMemoryFS
        from agent_eval.tools.tickets import FIXTURE, TicketStore

        files = dict(SEED_FILES)
        files.update(extra_files or {})
        return cls(fs=InMemoryFS(files), tickets=TicketStore.from_fixture(fixture or FIXTURE))

    def snapshot(self) -> dict[str, Any]:
        return {"files": dict(self.fs.files), "tickets": dict(self.tickets.tickets)}
