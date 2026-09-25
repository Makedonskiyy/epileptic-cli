"""Rendering: streaming markdown, tool-call traces, diffs, approval prompts."""

from __future__ import annotations

import difflib
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from epilepticcli.ui.theme import (
    BAD,
    FAINT,
    FAINTER,
    GLYPH_ASSISTANT,
    GLYPH_ERR,
    GLYPH_OK,
    GLYPH_TOOL,
    GLYPH_USER,
    GOOD,
    LAVENDER,
    LILAC,
    MAGENTA,
    THEME,
    VIOLET,
    VIOLET_DEEP,
    VIOLET_DIM,
)


def make_console() -> Console:
    return Console(theme=THEME, highlight=False, soft_wrap=False)


def user_echo(console: Console, text: str) -> None:
    console.print()
    console.print(Text(f"{GLYPH_USER} ", style=f"bold {VIOLET}") + Text(text, style="#fafafa"))


class StreamRenderer:
    """Live-updating markdown view while tokens stream in."""

    REFRESH = 0.06

    def __init__(self, console: Console) -> None:
        self.console = console
        self.buf: list[str] = []
        self._live: Live | None = None
        self._last = 0.0

    def __enter__(self) -> StreamRenderer:
        self.console.print(Text(f"{GLYPH_ASSISTANT} ", style=f"bold {MAGENTA}"))
        self._live = Live("", console=self.console, refresh_per_second=12, transient=False)
        self._live.start()
        return self

    def feed(self, chunk: str) -> None:
        self.buf.append(chunk)
        now = time.monotonic()
        if now - self._last >= self.REFRESH:
            self._last = now
            self._render()

    def _render(self) -> None:
        if self._live is None:
            return
        text = "".join(self.buf)
        try:
            renderable = Padding(Markdown(text), (0, 0, 0, 2))
        except Exception:
            renderable = Padding(Text(text), (0, 0, 0, 2))
        self._live.update(renderable)

    def __exit__(self, *exc) -> None:
        self._render()
        if self._live:
            self._live.stop()
            self._live = None
        if not "".join(self.buf).strip():
            self.console.print(Text("  (no output)", style=f"italic {FAINT}"))


def tool_start(console: Console, name: str, summary: str) -> None:
    line = Text()
    line.append(f"  {GLYPH_TOOL} ", style=f"{VIOLET_DEEP}")
    line.append(name, style=f"bold {LAVENDER}")
    if summary:
        line.append(f"  {summary}", style=f"{FAINT}")
    console.print(line)


def tool_end(console: Console, is_error: bool, preview: str) -> None:
    if not preview:
        return
    lines = preview.splitlines()[:4]
    color = BAD if is_error else FAINTER
    for ln in lines:
        console.print(Text(f"    {GLYPH_ERR if is_error else '│'} {ln[:160]}", style=f"{color}"))
    if len(preview.splitlines()) > 4:
        console.print(Text("    │ …", style=f"{FAINTER}"))


def status(console: Console, text: str) -> None:
    console.print(Text(f"  {GLYPH_OK} {text}", style=f"{VIOLET_DIM}"))


def error(console: Console, text: str) -> None:
    console.print(Text(f"  {GLYPH_ERR} {text}", style=f"{BAD}"))


def info_panel(console: Console, title: str, body: str) -> None:
    console.print(
        Panel(
            Text(body, style="#fafafa"),
            title=title,
            border_style=VIOLET_DIM,
            padding=(0, 1),
        )
    )


def diff_preview(console: Console, path: Path, old: str, new: str) -> None:
    try:
        current = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        current = ""
    updated = current.replace(old, new, 1)
    diff = difflib.unified_diff(
        current.splitlines(), updated.splitlines(), lineterm="", n=2
    )
    text = Text()
    for ln in list(diff)[2:60]:
        if ln.startswith("+"):
            text.append(ln + "\n", style=f"{GOOD}")
        elif ln.startswith("-"):
            text.append(ln + "\n", style=f"{BAD}")
        else:
            text.append(ln + "\n", style=f"{FAINT}")
    console.print(Panel(text, title=str(path), border_style=VIOLET_DIM, padding=(0, 1)))


def ask_approval(console: Console, tool_name: str, summary: str) -> str:
    """Return 'y', 'n', or 'a' (always for this tool)."""
    console.print(
        Text(
            f"  {GLYPH_TOOL} {tool_name} wants to run: {summary}",
            style=f"{LILAC}",
        )
    )
    try:
        answer = console.input(
            Text("  allow? [y]es / [n]o / [a]lways ", style=f"bold {VIOLET}")
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "n"
    return answer[:1] if answer[:1] in ("y", "n", "a") else "n"


def table(console: Console, headers: list[str], rows: list[list[str]]) -> None:
    from rich.table import Table

    t = Table(border_style=VIOLET_DIM, header_style=f"bold {LAVENDER}", pad_edge=False)
    for h in headers:
        t.add_column(h, style="#fafafa")
    for r in rows:
        t.add_row(*r)
    console.print(t)
