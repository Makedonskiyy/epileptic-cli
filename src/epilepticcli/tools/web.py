"""Web fetch tool - GET a URL, return readable text."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

from epilepticcli.tools.base import Tool, ToolResult, obj, trunc


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", raw)).strip()


def make_tools() -> list[Tool]:
    def web_fetch(url: str) -> ToolResult:
        try:
            resp = httpx.get(
                url,
                follow_redirects=True,
                timeout=20,
                headers={"User-Agent": "EpilepticCLI/0.1 (+https://github.com/Makedonskiyy/epileptic-cli)"},
            )
        except httpx.HTTPError as e:
            return ToolResult(f"Fetch failed: {e}", is_error=True)
        ctype = resp.headers.get("content-type", "")
        if "html" in ctype:
            parser = _TextExtractor()
            parser.feed(resp.text)
            body = parser.text()
        else:
            body = resp.text
        return ToolResult(trunc(f"[{resp.status_code}] {resp.url}\n\n{body}", 30_000))

    return [
        Tool(
            name="web_fetch",
            description="Fetch a URL and return its text content (HTML is stripped to readable text).",
            parameters=obj({"url": {"type": "string"}}, ["url"]),
            func=web_fetch,
            summarize=lambda a: a.get("url", ""),
        )
    ]
