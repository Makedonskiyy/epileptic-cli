"""EpilepticCLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epilepticcli import APP_NAME, __author__, __version__
from epilepticcli.app import App
from epilepticcli.ui import render


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="epileptic",
        description=f"{APP_NAME} - multi-provider AI terminal client, by {__author__}.",
        epilog="Inside the REPL: /help for commands, ! for shell, @file to attach files.",
    )
    p.add_argument("-p", "--prompt", help="one-shot prompt: run once and print the answer")
    p.add_argument("--provider", help="provider name (preset or from config.yaml)")
    p.add_argument("--model", help="model name")
    p.add_argument("--agent", help="agent definition to activate")
    p.add_argument("--system-prompt", help="extra text appended to the system prompt")
    p.add_argument("--system-prompt-file", help="file appended to the system prompt")
    p.add_argument(
        "--raw-system",
        action="store_true",
        help="send only your custom system prompt - no built-in prompt layers",
    )
    p.add_argument("--permission", choices=["ask", "auto"], help="tool permission mode")
    p.add_argument("--resume", metavar="SESSION_ID", help="resume a saved session")
    p.add_argument("-C", "--cwd", default=".", help="working directory")
    p.add_argument("--no-banner", action="store_true", help="skip the banner")
    p.add_argument("-V", "--version", action="version", version=f"{APP_NAME} {__version__}")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cwd = Path(args.cwd)

    extra = args.system_prompt
    if args.system_prompt_file:
        try:
            extra = ((extra + "\n\n") if extra else "") + Path(args.system_prompt_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"cannot read --system-prompt-file: {e}", file=sys.stderr)
            sys.exit(2)

    app = App(
        cwd=cwd,
        provider_name=args.provider,
        model=args.model,
        agent_name=args.agent,
        extra_system=extra,
        raw_mode=args.raw_system,
        permission_mode=args.permission,
    )

    if args.resume:
        from epilepticcli.core.session import Session

        try:
            s = Session.load(args.resume)
            app.messages = s.messages or app.messages[:1]
            app.session = s
        except (OSError, ValueError) as e:
            render.error(app.console, f"cannot resume: {e}")

    if args.prompt is not None:
        app._no_banner = True
        if sys.stdout.isatty():
            app.chat(args.prompt)
        else:
            _one_shot(app, args.prompt)
        return

    if args.no_banner:
        app.console.clear()
    app.run()


def _one_shot(app: App, text: str) -> None:
    """Non-interactive mode for pipes/scripts: raw deltas on stdout, traces on stderr."""
    app.messages.append({"role": "user", "content": text})
    enabled = app.agent.tools if (app.agent and app.agent.tools) else None
    from epilepticcli.core.agent import run_agent_turn

    def delta(chunk: str) -> None:
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def event(kind: str, payload: dict) -> None:
        if kind == "tool_start":
            print(f"[tool] {payload['name']}", file=sys.stderr)

    msg = run_agent_turn(
        app.messages, app.provider, app.model, app.tools,
        max_rounds=app.cfg.max_tool_rounds, on_delta=delta, on_tool_event=event,
        approve=lambda tool, args: app.permission_mode == "auto",
        enabled_tools=enabled,
    )
    sys.stdout.write("\n")
    app.session.input_tokens += msg.usage.input_tokens
    app.session.output_tokens += msg.usage.output_tokens
    app.session.messages = app.messages
    app.session.save()


if __name__ == "__main__":
    main()
