"""Deterministic fake web: keyword search and page fetch over a JSON fixture.

The fixture holds a dozen small pages that link to each other plus a few *designated error
URLs* that fail the same way every time (a 404, a timeout). ``web_search`` ranks pages by
keyword overlap with the query; ``web_fetch`` returns a page's text and its outgoing links.
Nothing touches the network, so a research task replays byte-for-byte.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_eval.tools.base import Tool, ToolError, obj_schema
from agent_eval.tools.sandbox import Sandbox

FIXTURE = Path(__file__).parent / "fixtures" / "web.json"
MAX_RESULTS = 5
SNIPPET_CHARS = 120
ERROR_KINDS = ("404", "timeout")

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from", "how", "in"}
    | {"is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "what", "which"}
    | {"who", "with"}
)


def tokenize(text: str) -> set[str]:
    """Lower-case alphanumeric tokens of two or more characters, minus stop words."""
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 2 and t not in _STOPWORDS}


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    body: str
    links: tuple[str, ...] = ()
    error: str | None = None  # "404" or "timeout" for designated error URLs

    def render(self) -> str:
        lines = [f"# {self.title}", self.url, "", self.body]
        if self.links:
            lines += ["", "Links:", *(f"- {u}" for u in self.links)]
        return "\n".join(lines)


@dataclass
class WebStore:
    pages: dict[str, Page]
    fetched: list[str] = field(default_factory=list)  # every fetch attempt, in order

    @classmethod
    def from_fixture(cls, path: Path = FIXTURE) -> WebStore:
        data = json.loads(path.read_text(encoding="utf-8"))
        pages: dict[str, Page] = {}
        for raw in data["pages"]:
            pages[raw["url"]] = Page(
                raw["url"], raw["title"], raw["body"], tuple(raw.get("links", []))
            )
        for raw in data.get("errors", []):
            if raw["kind"] not in ERROR_KINDS:
                raise ValueError(f"web fixture: unknown error kind {raw['kind']!r}")
            pages[raw["url"]] = Page(
                raw["url"], raw["title"], raw.get("snippet", ""), error=raw["kind"]
            )
        return cls(pages)

    def search(self, query: str, limit: int = MAX_RESULTS) -> list[tuple[int, Page]]:
        """Rank pages by distinct query tokens found in title (weight 2) and body (weight 1)."""
        terms = tokenize(query)
        if not terms:
            return []
        scored: list[tuple[int, Page]] = []
        for page in self.pages.values():
            title, body = tokenize(page.title), tokenize(page.body)
            score = sum(2 * (t in title) + (t in body) for t in terms)
            if score:
                scored.append((score, page))
        scored.sort(key=lambda s: (-s[0], s[1].url))
        return scored[:limit]

    def fetch(self, url: str) -> Page:
        self.fetched.append(url)
        if not url.startswith("https://"):
            raise ToolError(f"invalid url {url!r}: must be absolute and start with https://")
        page = self.pages.get(url)
        if page is None:  # a trailing slash is not a different page, in either direction
            page = self.pages.get(url[:-1] if url.endswith("/") else url + "/")
        if page is None:
            raise ToolError(f"404 Not Found: {url}")
        if page.error == "404":
            raise ToolError(f"404 Not Found: {url} (this page has been removed)")
        if page.error == "timeout":
            raise ToolError(f"timeout: {url} did not respond within 10 seconds")
        return page


def _snippet(page: Page, terms: set[str]) -> str:
    """First body line that mentions a query term, else the first line; trimmed."""
    lines = [ln for ln in page.body.splitlines() if ln.strip()]
    hit = next((ln for ln in lines if tokenize(ln) & terms), lines[0] if lines else "")
    return hit if len(hit) <= SNIPPET_CHARS else hit[: SNIPPET_CHARS - 3] + "..."


def _search(sb: Sandbox, args: dict[str, Any]) -> str:
    query = args["query"]
    hits = sb.web.search(query)
    if not hits:
        return f"no results for {query!r}"
    terms = tokenize(query)
    lines = [f"{len(hits)} results for {query!r}:"]
    for i, (_, page) in enumerate(hits, 1):
        lines.append(f"{i}. {page.url} - {page.title}")
        lines.append(f"   {_snippet(page, terms)}")
    return "\n".join(lines)


def _fetch(sb: Sandbox, args: dict[str, Any]) -> str:
    return sb.web.fetch(args["url"]).render()


WEB_TOOLS: list[Tool] = [
    Tool(
        "web_search",
        "Search the web by keywords. Returns up to 5 results ranked by keyword overlap, each "
        "with a URL, a title and a one-line snippet.",
        obj_schema({"query": {"type": "string"}}, ["query"]),
        _search,
    ),
    Tool(
        "web_fetch",
        "Fetch a page by absolute https URL. Returns its title, text and outgoing links. "
        "Missing pages return a 404 error; unreachable hosts time out.",
        obj_schema({"url": {"type": "string"}}, ["url"]),
        _fetch,
    ),
]
