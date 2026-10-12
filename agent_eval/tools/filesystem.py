"""Deterministic in-memory file system with read, write, list and search tools."""

from __future__ import annotations

from typing import Any

from agent_eval.tools.base import Tool, ToolError, obj_schema
from agent_eval.tools.sandbox import Sandbox


def _norm(path: str) -> str:
    if not path.startswith("/"):
        raise ToolError(f"path must be absolute (start with '/'): {path!r}")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ToolError(f"path may not contain '..': {path!r}")
    return "/" + "/".join(parts)


class InMemoryFS:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files: dict[str, str] = {_norm(k): v for k, v in (files or {}).items()}

    def read(self, path: str) -> str:
        path = _norm(path)
        if path in self.files:
            return self.files[path]
        if self._is_dir(path):
            raise ToolError(f"{path} is a directory, not a file")
        raise ToolError(f"file not found: {path}")

    def write(self, path: str, content: str) -> None:
        path = _norm(path)
        if path == "/" or self._is_dir(path):
            raise ToolError(f"{path} is a directory")
        parts = path.split("/")[1:-1]
        for i in range(1, len(parts) + 1):
            ancestor = "/" + "/".join(parts[:i])
            if ancestor in self.files:
                raise ToolError(f"{ancestor} is a file, not a directory")
        self.files[path] = content

    def listdir(self, path: str) -> list[str]:
        path = _norm(path)
        if path in self.files:
            raise ToolError(f"{path} is a file, not a directory")
        prefix = "/" if path == "/" else path + "/"
        entries: set[str] = set()
        for f in self.files:
            if f.startswith(prefix):
                rest = f[len(prefix) :].split("/", 1)
                entries.add(rest[0] + ("/" if len(rest) > 1 else ""))
        if not entries and path != "/":
            raise ToolError(f"directory not found: {path}")
        return sorted(entries)

    def search(self, query: str, root: str = "/") -> list[str]:
        root = _norm(root)
        prefix = "/" if root == "/" else root + "/"
        hits = []
        for f, content in sorted(self.files.items()):
            if f.startswith(prefix) and query.lower() in content.lower():
                hits.append(f)
        return hits

    def _is_dir(self, path: str) -> bool:
        prefix = "/" if path == "/" else path + "/"
        return any(f.startswith(prefix) for f in self.files)


def _read(sb: Sandbox, args: dict[str, Any]) -> str:
    return sb.fs.read(args["path"])


def _write(sb: Sandbox, args: dict[str, Any]) -> str:
    sb.fs.write(args["path"], args["content"])
    return f"wrote {len(args['content'])} characters to {_norm(args['path'])}"


def _list(sb: Sandbox, args: dict[str, Any]) -> str:
    entries = sb.fs.listdir(args.get("path", "/"))
    return "\n".join(entries) if entries else "(empty)"


def _search(sb: Sandbox, args: dict[str, Any]) -> str:
    hits = sb.fs.search(args["query"], args.get("path", "/"))
    return "\n".join(hits) if hits else "no matches"


FS_TOOLS: list[Tool] = [
    Tool(
        "fs_read",
        "Read the full contents of a file at an absolute path.",
        obj_schema({"path": {"type": "string"}}, ["path"]),
        _read,
    ),
    Tool(
        "fs_write",
        "Create or overwrite a file with the given text content.",
        obj_schema(
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]
        ),
        _write,
    ),
    Tool(
        "fs_list",
        "List entries in a directory. Sub-directories end with '/'.",
        obj_schema({"path": {"type": "string"}}, []),
        _list,
    ),
    Tool(
        "fs_search",
        "Case-insensitive search for text inside files; returns matching paths.",
        obj_schema({"query": {"type": "string"}, "path": {"type": "string"}}, ["query"]),
        _search,
    ),
]
