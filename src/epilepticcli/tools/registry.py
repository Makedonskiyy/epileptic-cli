"""Assemble the tool set for a working directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epilepticcli.tools import files, shell, web
from epilepticcli.tools.base import Tool, ToolResult


def build_tools(cwd: Path) -> dict[str, Tool]:
    tools: dict[str, Tool] = {}
    for t in files.make_tools(cwd) + shell.make_tools(cwd) + web.make_tools():
        tools[t.name] = t
    return tools


def specs(tools: dict[str, Tool]) -> list[dict[str, Any]]:
    return [t.spec() for t in tools.values()]


def run_tool(tools: dict[str, Tool], name: str, arguments: str) -> ToolResult:
    tool = tools.get(name)
    if tool is None:
        return ToolResult(f"Unknown tool: {name}", is_error=True)
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as e:
        return ToolResult(f"Invalid JSON arguments: {e}", is_error=True)
    try:
        return tool.func(**args)
    except TypeError as e:
        return ToolResult(f"Bad arguments for {name}: {e}", is_error=True)
    except Exception as e:  # noqa: BLE001 - tool errors become model-visible results
        return ToolResult(f"{name} failed: {e}", is_error=True)
