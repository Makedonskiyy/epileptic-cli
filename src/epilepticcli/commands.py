"""Slash commands. dispatch(app, "cmd rest...") -> bool (False = exit)."""

from __future__ import annotations

import os
import subprocess
import sys

from epilepticcli.config import AGENTS_DIR, CONFIG_FILE, SYSTEM_PROMPT_FILE
from epilepticcli.core.agents import list_agents
from epilepticcli.core.session import Session, list_sessions
from epilepticcli.providers.registry import PRESETS, known_providers, resolve_env_key
from epilepticcli.ui import render
from epilepticcli.ui.theme import GLYPH_SEP


def descriptions() -> dict[str, str]:
    return {name: fn.__doc__.split("\n")[0] if fn.__doc__ else "" for name, fn in _HANDLERS.items()}


def dispatch(app, line: str) -> bool:
    parts = line.split(maxsplit=1)
    name = parts[0].lstrip("/") if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    fn = _HANDLERS.get(name)
    if fn is None:
        render.error(app.console, f"unknown command /{name} - try /help")
        return True
    return fn(app, arg)


def _help(app, arg: str) -> bool:
    """Show all commands."""
    rows = [[f"/{n}", d] for n, d in descriptions().items()]
    render.table(app.console, ["command", "what it does"], rows)
    app.console.print(f"  {GLYPH_SEP} ! cmd - run shell   {GLYPH_SEP} @file - attach file   {GLYPH_SEP} /exit - quit")
    return True


def _model(app, arg: str) -> bool:
    """Show or switch the model: /model [name]"""
    if not arg:
        render.status(app.console, f"model: {app.model}")
        return True
    app.set_model(arg.strip())
    return True


def _provider(app, arg: str) -> bool:
    """Show or switch the provider: /provider [name]"""
    if not arg:
        render.status(app.console, f"provider: {app.provider_name}")
        return True
    app.set_provider(arg.strip())
    return True


def _providers(app, arg: str) -> bool:
    """List all known providers and key status."""
    rows = []
    for name in known_providers(app.cfg):
        preset = PRESETS.get(name)
        pc = app.cfg.providers.get(name)
        env_key = resolve_env_key(name)
        key = "yes" if (env_key and os.environ.get(env_key)) or (pc and pc.api_key) else ("n/a" if not env_key else "missing")
        rows.append(
            [
                ("▸ " if name == app.provider_name else "") + name,
                (pc.type if pc else preset.type if preset else "openai"),
                (pc.base_url if pc and pc.base_url else preset.base_url if preset else "") or "-",
                env_key or "-",
                key,
            ]
        )
    render.table(app.console, ["name", "type", "base_url", "env key", "key"], rows)
    return True


def _system(app, arg: str) -> bool:
    """System prompt control: /system show | edit | raw on|off | clear"""
    sub = arg.strip().split() if arg else ["show"]
    action = sub[0]
    if action == "show":
        content = app.messages[0]["content"] if app.messages and app.messages[0].get("role") == "system" else "(none)"
        render.info_panel(app.console, f"effective system prompt ({len(content)} chars)", content[:6000])
        if len(content) > 6000:
            render.status(app.console, f"… truncated, {len(content)} chars total")
    elif action == "raw":
        on = len(sub) < 2 or sub[1].lower() in ("on", "true", "1")
        app.raw_mode = on
        app._reset_system_prompt()
        render.status(app.console, f"raw system mode {'ON - only your prompt is sent' if on else 'OFF'}")
    elif action == "edit":
        SYSTEM_PROMPT_FILE.touch(exist_ok=True)
        editor = os.environ.get("EDITOR") or ("notepad" if sys.platform == "win32" else "nano")
        subprocess.run([editor, str(SYSTEM_PROMPT_FILE)])
        app._reset_system_prompt()
        render.status(app.console, f"edited {SYSTEM_PROMPT_FILE}")
    elif action == "clear":
        if SYSTEM_PROMPT_FILE.exists():
            SYSTEM_PROMPT_FILE.unlink()
        app._reset_system_prompt()
        render.status(app.console, "custom system_prompt.md removed")
    else:
        render.error(app.console, "usage: /system show | edit | raw on|off | clear")
    return True


def _agents(app, arg: str) -> bool:
    """List agent definitions."""
    app.agents = list_agents(app.cwd)
    if not app.agents:
        render.status(app.console, "no agents found - create .epilepticcli/agents/*.md or run /init")
        return True
    rows = [
        [
            ("▸ " if app.agent and app.agent.name == a.name else "") + a.name,
            a.description[:50],
            a.provider or "-",
            a.model or "-",
            str(a.path),
        ]
        for a in app.agents.values()
    ]
    render.table(app.console, ["name", "description", "provider", "model", "file"], rows)
    return True


def _agent(app, arg: str) -> bool:
    """Switch agent: /agent <name> | /agent none"""
    app.agents = list_agents(app.cwd)
    if not arg:
        return _agents(app, arg)
    app.set_agent(arg.strip())
    return True


def _init(app, arg: str) -> bool:
    """Scaffold EPIC.md + .epilepticcli/agents/example.md in cwd."""
    epic = app.cwd / "EPIC.md"
    agents_dir = app.cwd / ".epilepticcli" / "agents"
    if not epic.exists():
        epic.write_text(
            "# Project memory\n\nDescribe the project, its conventions, and how to work in it.\n"
            "Everything here is injected into the system prompt.\n",
            encoding="utf-8",
        )
    agents_dir.mkdir(parents=True, exist_ok=True)
    example = agents_dir / "example.md"
    if not example.exists():
        example.write_text(
            "---\nname: example\ndescription: minimal agent template\ntools: [read_file, glob, grep]\n---\n\n"
            "You are a focused helper. Answer briefly, cite files by path.\n",
            encoding="utf-8",
        )
    render.status(app.console, f"created {epic} + {example}")
    return True


def _clear(app, arg: str) -> bool:
    """Clear conversation history (system prompt is kept)."""
    app.messages = app.messages[:1]
    render.status(app.console, "history cleared")
    return True


def _compact(app, arg: str) -> bool:
    """Summarize the conversation into a single context message."""
    if len(app.messages) < 4:
        render.status(app.console, "nothing to compact")
        return True
    history = app.messages[1:]
    transcript = "\n".join(
        f"{m.get('role')}: {str(m.get('content') or '')[:2000]}" for m in history
    )
    try:
        summary = app.provider.complete(
            [
                {"role": "system", "content": "Summarize this conversation faithfully: decisions made, files touched, open questions. Be compact."},
                {"role": "user", "content": transcript},
            ],
            app.model,
            max_tokens=1024,
        )
    except Exception as e:  # noqa: BLE001
        render.error(app.console, f"compact failed: {e}")
        return True
    app.messages = app.messages[:1] + [
        {"role": "user", "content": f"[conversation summary]\n{summary}"},
        {"role": "assistant", "content": "Understood - I have the summary of our work so far."},
    ]
    render.status(app.console, f"compacted {len(history)} messages")
    return True


def _export(app, arg: str) -> bool:
    """Export the transcript to markdown."""
    app.session.messages = app.messages
    out = app.session.export_markdown()
    render.status(app.console, f"exported → {out}")
    return True


def _sessions(app, arg: str) -> bool:
    """List saved sessions."""
    rows = [
        [s.get("file", "?"), s.get("provider", "?"), s.get("model", "?"),
         f"{s.get('input_tokens', 0)}+{s.get('output_tokens', 0)}"]
        for s in list_sessions()[:20]
    ]
    if not rows:
        render.status(app.console, "no saved sessions")
        return True
    render.table(app.console, ["id", "provider", "model", "tokens in+out"], rows)
    app.console.print("  resume with /resume <id>")
    return True


def _resume(app, arg: str) -> bool:
    """Resume a saved session: /resume <id>"""
    if not arg:
        return _sessions(app, arg)
    try:
        s = Session.load(arg.strip())
    except (OSError, ValueError) as e:
        render.error(app.console, f"cannot load session: {e}")
        return True
    app.messages = s.messages or app.messages[:1]
    app.session = s
    render.status(app.console, f"resumed session {s.id} ({len(s.messages)} messages)")
    return True


def _cost(app, arg: str) -> bool:
    """Show token usage for this session."""
    s = app.session
    render.status(
        app.console,
        f"tokens: {s.input_tokens} in / {s.output_tokens} out (usage reported by provider)",
    )
    return True


def _permissions(app, arg: str) -> bool:
    """Permission mode: /permissions ask|auto"""
    if not arg:
        render.status(app.console, f"mode: {app.permission_mode} · always-allowed: {sorted(app.always_allowed) or '[]'}")
        return True
    mode = arg.strip().lower()
    if mode not in ("ask", "auto"):
        render.error(app.console, "usage: /permissions ask|auto")
        return True
    app.permission_mode = mode
    if mode == "ask":
        app.always_allowed.clear()
    render.status(app.console, f"permission mode → {mode}")
    return True


def _config(app, arg: str) -> bool:
    """Show config location and effective settings."""
    rows = [
        ["config", str(CONFIG_FILE)],
        ["agents", str(AGENTS_DIR)],
        ["system_prompt.md", str(SYSTEM_PROMPT_FILE)],
        ["provider", app.provider_name],
        ["model", app.model],
        ["permissions", app.permission_mode],
        ["builtin_system_prompt", str(app.cfg.builtin_system_prompt)],
        ["raw mode", str(app.raw_mode)],
        ["cwd", str(app.cwd)],
    ]
    render.table(app.console, ["setting", "value"], rows)
    return True


def _exit(app, arg: str) -> bool:
    """Quit EpilepticCLI."""
    return False


_HANDLERS = {
    "help": _help,
    "model": _model,
    "provider": _provider,
    "providers": _providers,
    "system": _system,
    "agent": _agent,
    "agents": _agents,
    "init": _init,
    "clear": _clear,
    "compact": _compact,
    "export": _export,
    "sessions": _sessions,
    "resume": _resume,
    "cost": _cost,
    "permissions": _permissions,
    "config": _config,
    "exit": _exit,
    "quit": _exit,
    "q": _exit,
}
