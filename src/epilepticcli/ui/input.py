"""Input: prompt_toolkit session with /command and @file completion."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PtStyle

from epilepticcli.config import HISTORY_FILE
from epilepticcli.ui.theme import VIOLET

PT_STYLE = PtStyle.from_dict(
    {
        "completion-menu.completion": "bg:#1e1b29 #c084fc",
        "completion-menu.completion.current": "bg:#7c3aed #fafafa",
        "completion-menu.meta.completion": "bg:#1e1b29 #6d28d9",
        "completion-menu.meta.completion.current": "bg:#7c3aed #e9d5ff",
        "bottom-toolbar": "bg:#0a0a0f #6d28d9",
    }
)


def _iter_files(cwd: Path, limit: int = 300) -> Iterable[str]:
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    count = 0
    for p in sorted(cwd.rglob("*")):
        if count >= limit:
            break
        if any(part in skip for part in p.parts):
            continue
        try:
            yield str(p.relative_to(cwd))
            count += 1
        except ValueError:
            continue


class EpiCompleter(Completer):
    def __init__(self, commands: dict[str, str], cwd: Path) -> None:
        self.commands = commands  # name -> description
        self.cwd = cwd

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        if text.lstrip().startswith("/") and " " not in text.lstrip():
            prefix = text.lstrip()[1:]
            for name, desc in self.commands.items():
                if name.startswith(prefix):
                    yield Completion(
                        name,
                        start_position=-len(word),
                        display="/" + name,
                        display_meta=desc,
                    )
            return

        if word.startswith("@"):
            frag = word[1:].lower()
            for path in _iter_files(self.cwd):
                if frag in path.lower():
                    yield Completion(
                        "@" + path,
                        start_position=-len(word),
                        display="@" + path,
                    )


def make_session(cwd: Path, commands: dict[str, str]) -> PromptSession:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    return PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        completer=EpiCompleter(commands, cwd),
        style=PT_STYLE,
        complete_while_typing=True,
    )


def prompt_str(provider: str, model: str) -> HTML:
    return HTML(
        f'<style fg="{VIOLET}">▚ </style>'
        f'<style fg="#4c1d95">{provider}</style>'
        f'<style fg="#3f3f46">:</style>'
        f'<style fg="#6d28d9">{model}</style>'
        f'<style fg="{VIOLET}"> ❯ </style>'
    )


def bottom_bar(mode: str) -> HTML:
    return HTML(
        f'<style fg="#4c1d95"> ⌬ {mode} mode · /help for commands · ! for shell · @ to attach files </style>'
    )
