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
    p.add_argument(
        "command",
        nargs="*",
        help="subcommand: 'setup' | 'update' | 'key set|remove' | 'provider add <name> <base_url> [type] [models]'",
    )
    p.add_argument("-V", "--version", action="version", version=f"{APP_NAME} {__version__}")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cwd = Path(args.cwd)

    if args.command:
        _subcommand(args.command)
        return

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
        if sys.stdout.isatty():
            app.chat(args.prompt)
        else:
            _one_shot(app, args.prompt)
        return

    app.run(banner=not args.no_banner)


def _subcommand(argv: list[str]) -> None:
    """epileptic setup | update | key set|remove ..."""
    from epilepticcli.commands import run_setup_wizard
    from epilepticcli.config import ensure_provider_entry, load_config, save_config
    from epilepticcli.core.update import self_update

    cmd, rest = argv[0], argv[1:]
    if cmd == "setup":
        app = App(cwd=Path.cwd())
        run_setup_wizard(app)
    elif cmd == "update":
        print(self_update())
    elif cmd == "key" and len(rest) == 2 and rest[0] == "set":
        print("usage: epileptic key set <provider> <api_key>", file=sys.stderr)
        sys.exit(2)
    elif cmd == "key" and len(rest) == 3 and rest[0] == "set":
        cfg = load_config()
        pc = ensure_provider_entry(cfg, rest[1])
        pc.api_key = rest[2]
        save_config(cfg)
        print(f"key for {rest[1]} saved")
    elif cmd == "key" and len(rest) == 2 and rest[0] == "remove":
        cfg = load_config()
        pc = cfg.providers.get(rest[1])
        if pc:
            pc.api_key = None
            save_config(cfg)
        print(f"stored key for {rest[1]} removed")
    elif cmd == "provider" and rest and rest[0] == "add":
        # epileptic provider add <name> <base_url> [openai|anthropic] [model,model,...]
        if len(rest) < 3:
            print("usage: epileptic provider add <name> <base_url> [openai|anthropic] [model1,model2,...]",
                  file=sys.stderr)
            sys.exit(2)
        name, base_url = rest[1], rest[2]
        ptype = rest[3] if len(rest) > 3 else "openai"
        if ptype not in ("openai", "anthropic"):
            print(f"unknown protocol '{ptype}' - use openai or anthropic", file=sys.stderr)
            sys.exit(2)
        models = [m.strip() for m in rest[4].split(",") if m.strip()] if len(rest) > 4 else []
        cfg = load_config()
        pc = cfg.providers.get(name) or ensure_provider_entry(cfg, name)
        pc.type, pc.base_url = ptype, base_url
        if models:
            pc.models = models
        save_config(cfg)
        print(f"provider {name} saved ({ptype} @ {base_url}) - then: epileptic key set {name} <key>")
    else:
        print(f"unknown command: {' '.join(argv)}", file=sys.stderr)
        sys.exit(2)


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
