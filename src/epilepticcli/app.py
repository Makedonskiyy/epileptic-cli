"""EpilepticCLI application: REPL, command dispatch, agent turns."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from epilepticcli import commands as slash_commands
from epilepticcli.config import Config, load_config
from epilepticcli.core.agent import run_agent_turn
from epilepticcli.core.agents import Agent, list_agents
from epilepticcli.core.prompts import compose_system_prompt
from epilepticcli.core.session import Session
from epilepticcli.providers.base import Provider
from epilepticcli.providers.registry import build_provider
from epilepticcli.tools.base import Tool
from epilepticcli.tools.registry import build_tools
from epilepticcli.ui import render
from epilepticcli.ui.banner import render as render_banner
from epilepticcli.ui.input import bottom_bar, make_session, prompt_str


class App:
    def __init__(
        self,
        cwd: Path,
        provider_name: str | None = None,
        model: str | None = None,
        agent_name: str | None = None,
        extra_system: str | None = None,
        raw_mode: bool = False,
        permission_mode: str | None = None,
    ) -> None:
        self.cwd = cwd.resolve()
        self.cfg: Config = load_config()
        self.provider_name = provider_name or self.cfg.default_provider
        self.model = model or self.cfg.default_model
        self.permission_mode = permission_mode or self.cfg.permission_mode
        self.raw_mode = raw_mode
        self.extra_system = extra_system
        self.agent: Agent | None = None
        self.always_allowed: set[str] = set()

        self.console = render.make_console()
        self.tools: dict[str, Tool] = build_tools(self.cwd)
        self.provider: Provider = self._build_provider(self.provider_name)
        self.agents = list_agents(self.cwd)
        if agent_name:
            self.set_agent(agent_name)

        self.messages: list[dict[str, Any]] = []
        self.session = Session.new(self.provider_name, self.model)
        self._reset_system_prompt()

    # ---- wiring -----------------------------------------------------------

    def _build_provider(self, name: str) -> Provider:
        try:
            return build_provider(self.cfg, name)
        except KeyError as e:
            render.error(self.console, str(e))
            raise SystemExit(2) from e
        except Exception as e:
            render.error(self.console, f"Provider '{name}' failed to initialize: {e}")
            raise SystemExit(2) from e

    def set_provider(self, name: str) -> None:
        self.provider = self._build_provider(name)
        self.provider_name = name
        self.session.provider = name
        render.status(self.console, f"provider → {name}")

    def set_model(self, model: str) -> None:
        self.model = model
        self.session.model = model
        render.status(self.console, f"model → {model}")

    def set_agent(self, name: str) -> None:
        if name in ("none", "off", "-"):
            self.agent = None
            self._reset_system_prompt()
            render.status(self.console, "agent cleared")
            return
        agent = self.agents.get(name)
        if agent is None:
            render.error(self.console, f"No agent '{name}'. Try /agents")
            return
        self.agent = agent
        if agent.provider:
            self.set_provider(agent.provider)
        if agent.model:
            self.set_model(agent.model)
        self._reset_system_prompt()
        render.status(self.console, f"agent → {agent.name} ({agent.path})")

    def _reset_system_prompt(self) -> None:
        prompt = compose_system_prompt(
            self.cfg,
            self.cwd,
            agent_prompt=self.agent.prompt if self.agent else None,
            extra=self.extra_system,
            raw_mode=self.raw_mode,
        )
        sysmsg = {"role": "system", "content": prompt}
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0] = sysmsg
        else:
            self.messages.insert(0, sysmsg)

    # ---- input handling ----------------------------------------------------

    def handle(self, text: str) -> bool:
        """Returns False when the app should exit."""
        text = text.strip()
        if not text:
            return True
        if text.startswith("!"):
            self._shell(text[1:])
            return True
        if text.startswith("/"):
            return slash_commands.dispatch(self, text[1:])
        self.chat(self._expand_mentions(text))
        return True

    def _expand_mentions(self, text: str) -> str:
        """Expand @file tokens into inlined attachments."""
        out = text
        attachments: list[str] = []
        for token in text.split():
            if not token.startswith("@") or len(token) < 2:
                continue
            p = (self.cwd / token[1:]).resolve()
            if not p.is_file() or self.cwd not in (p, *p.parents):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            out = out.replace(token, p.name)
            attachments.append(f'<file path="{p}">\n{content[:200_000]}\n</file>')
        if attachments:
            out += "\n\n" + "\n\n".join(attachments)
        return out

    def _shell(self, command: str) -> None:
        command = command.strip()
        if not command:
            return
        render.tool_start(self.console, "shell", command)
        proc = subprocess.run(
            command, shell=True, cwd=self.cwd, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=600,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        render.tool_end(self.console, proc.returncode != 0, out[:2000])
        self.messages.append(
            {
                "role": "user",
                "content": f"! shell command `{command}` output:\n```\n{out[:10_000]}\n```",
            }
        )

    # ---- agent turn --------------------------------------------------------

    def _on_tool_event(self, kind: str, payload: dict[str, Any]) -> None:
        if kind == "tool_start":
            tool = self.tools.get(payload["name"])
            summary = tool.summary_line(payload.get("args", {})) if tool else ""
            render.tool_start(self.console, payload["name"], summary)
        else:
            render.tool_end(
                self.console,
                bool(payload.get("is_error")),
                str(payload.get("preview", "")),
            )

    def _approve(self, tool: Tool, args: dict[str, Any]) -> bool:
        if self.permission_mode == "auto" or tool.name in self.always_allowed:
            return True
        if tool.name == "edit_file":
            p = Path(args.get("path", ""))
            if not p.is_absolute():
                p = self.cwd / p
            render.diff_preview(self.console, p, str(args.get("old_string", "")), str(args.get("new_string", "")))
        answer = render.ask_approval(self.console, tool.name, tool.summary_line(args))
        if answer == "a":
            self.always_allowed.add(tool.name)
            return True
        return answer == "y"

    def chat(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        enabled = self.agent.tools if (self.agent and self.agent.tools) else None
        try:
            with render.StreamRenderer(self.console) as sr:
                msg = run_agent_turn(
                    self.messages,
                    self.provider,
                    self.model,
                    self.tools,
                    max_rounds=self.cfg.max_tool_rounds,
                    on_delta=sr.feed,
                    on_tool_event=self._on_tool_event,
                    approve=self._approve,
                    enabled_tools=enabled,
                )
        except KeyboardInterrupt:
            render.error(self.console, "interrupted")
            return
        except Exception as e:  # noqa: BLE001 - surface provider errors, keep REPL alive
            render.error(self.console, f"{type(e).__name__}: {e}")
            # drop the user message that failed so history stays consistent
            self.messages.pop()
            return
        self.session.input_tokens += msg.usage.input_tokens
        self.session.output_tokens += msg.usage.output_tokens
        self.session.messages = self.messages
        self.session.save()

    # ---- main loop ---------------------------------------------------------

    def run(self, banner: bool = True) -> None:
        if banner:
            render_banner(self.console)
        self._welcome_line()
        session = make_session(self.cwd, slash_commands.descriptions())
        while True:
            try:
                text = session.prompt(
                    prompt_str(self.provider_name, self.model),
                    bottom_toolbar=bottom_bar(self.permission_mode),
                )
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                break
            if not self.handle(text):
                break
        render.status(self.console, "session saved to ~/.epilepticcli/sessions")

    def _welcome_line(self) -> None:
        render.status(
            self.console,
            f"{self.provider_name} / {self.model} · cwd {self.cwd} · permissions {self.permission_mode}",
        )
        if self.agent:
            render.status(self.console, f"agent: {self.agent.name}")
