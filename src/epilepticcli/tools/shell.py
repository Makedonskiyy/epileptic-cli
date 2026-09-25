"""Shell tool - runs commands with a timeout. Approval-gated by default."""

from __future__ import annotations

import subprocess
from pathlib import Path

from epilepticcli.tools.base import Tool, ToolResult, obj, trunc

TIMEOUT = 120


def make_tools(cwd: Path) -> list[Tool]:
    def run_shell(command: str, timeout: int = TIMEOUT) -> ToolResult:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=min(timeout, 600),
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(f"Command timed out after {timeout}s", is_error=True)
        out = (proc.stdout or "") + (proc.stderr or "")
        status = f"exit {proc.returncode}"
        return ToolResult(trunc(out.strip() or f"(no output, {status})"), is_error=proc.returncode != 0)

    return [
        Tool(
            name="run_shell",
            description="Run a shell command in the working directory (cmd.exe on Windows, sh elsewhere).",
            parameters=obj(
                {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": TIMEOUT},
                },
                ["command"],
            ),
            func=run_shell,
            needs_approval=True,
            summarize=lambda a: a.get("command", ""),
        )
    ]
