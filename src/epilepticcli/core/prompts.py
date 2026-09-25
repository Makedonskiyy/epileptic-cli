"""System prompt composition.

Layers, in order:
  1. Built-in prompt (skipped entirely when `builtin_system_prompt: false`
     or --raw-system is used - the model sees exactly your text, which is
     what prompt-engineering / red-team experiments need).
  2. Active agent definition (~/.epilepticcli/agents/<name>.md or
     .epilepticcli/agents/<name>.md in the project).
  3. Project memory files in the working directory:
     EPIC.md, AGENTS.md, CLAUDE.md (all merged, in that order).
  4. Personal override: ~/.epilepticcli/system_prompt.md
  5. One-off prompt: --system-prompt / --system-prompt-file / /system set.
"""

from __future__ import annotations

from pathlib import Path

from epilepticcli.config import SYSTEM_PROMPT_FILE, Config

MEMORY_FILES = ("EPIC.md", "AGENTS.md", "CLAUDE.md")

BUILTIN_PROMPT = """\
You are EpilepticCLI, an AI coding and research assistant running in the user's terminal.

Environment: the user's real machine. Working directory: {cwd}.

Rules:
- Use tools to act, not just to advise. Read files before editing them.
- Prefer small, focused edits. Match the style of the surrounding code.
- Never expose secrets, tokens, or credentials in output.
- Before running destructive shell commands, confirm intent with the user.
- When a task is ambiguous, ask one precise question rather than guessing.
- Keep answers concise and technical. Code speaks; prose explains it.
"""


def compose_system_prompt(
    cfg: Config,
    cwd: Path,
    agent_prompt: str | None = None,
    extra: str | None = None,
    raw_mode: bool = False,
) -> str:
    parts: list[str] = []

    if cfg.builtin_system_prompt and not raw_mode:
        parts.append(BUILTIN_PROMPT.format(cwd=cwd))

    if agent_prompt:
        parts.append(agent_prompt)

    memory = []
    for name in MEMORY_FILES:
        f = cwd / name
        if f.is_file():
            memory.append(f"# {name}\n\n{f.read_text(encoding='utf-8', errors='replace')}")
    if memory:
        parts.append("\n\n".join(memory))

    if SYSTEM_PROMPT_FILE.is_file():
        parts.append(SYSTEM_PROMPT_FILE.read_text(encoding="utf-8"))

    if extra:
        parts.append(extra)

    return "\n\n---\n\n".join(p for p in parts if p.strip())
