"""Agent definitions: markdown files with YAML frontmatter.

Locations searched (project wins over global):
    .epilepticcli/agents/<name>.md
    ~/.epilepticcli/agents/<name>.md

Format:

    ---
    name: researcher
    description: careful web researcher
    provider: openrouter          # optional override
    model: anthropic/claude-...   # optional override
    tools: [read_file, grep, glob, web_fetch]   # optional whitelist
    ---
    System prompt body goes here. It IS the agent's prompt - write exactly
    the persona and constraints you want the model to see.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from epilepticcli.config import AGENTS_DIR


@dataclass
class Agent:
    name: str
    description: str
    prompt: str
    path: Path
    provider: str | None = None
    model: str | None = None
    tools: list[str] | None = None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    try:
        meta = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        meta = {}
    body = text[end + 4 :].lstrip("\n")
    return meta if isinstance(meta, dict) else {}, body


def load_agent(path: Path) -> Agent | None:
    try:
        meta, body = _split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    name = str(meta.get("name") or path.stem)
    return Agent(
        name=name,
        description=str(meta.get("description") or ""),
        prompt=body,
        path=path,
        provider=meta.get("provider"),
        model=meta.get("model"),
        tools=list(meta["tools"]) if meta.get("tools") else None,
    )


def list_agents(cwd: Path) -> dict[str, Agent]:
    agents: dict[str, Agent] = {}
    for d in (AGENTS_DIR, cwd / ".epilepticcli" / "agents"):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            agent = load_agent(f)
            if agent:
                agents[agent.name] = agent  # project dir shadows global on name clash
    return agents
