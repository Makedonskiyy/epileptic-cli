"""The agentic turn: call model -> run tools -> repeat until a final answer."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from epilepticcli.providers.base import AssistantMessage, Provider
from epilepticcli.tools.base import Tool, ToolResult
from epilepticcli.tools.registry import run_tool, specs

OnDelta = Callable[[str], None]
OnToolEvent = Callable[[str, dict[str, Any]], None]
Approve = Callable[[Tool, dict[str, Any]], bool]


def run_agent_turn(
    messages: list[dict[str, Any]],
    provider: Provider,
    model: str,
    tools: dict[str, Tool],
    *,
    max_rounds: int = 40,
    temperature: float | None = None,
    on_delta: OnDelta | None = None,
    on_tool_event: OnToolEvent | None = None,
    approve: Approve | None = None,
    enabled_tools: list[str] | None = None,
) -> AssistantMessage:
    active = tools
    if enabled_tools is not None:
        active = {n: t for n, t in tools.items() if n in enabled_tools}

    tool_specs = specs(active) if active and provider.supports_tools else None
    last = AssistantMessage()

    for _ in range(max_rounds):
        msg = provider.stream_chat(
            messages, model, tools=tool_specs, temperature=temperature, on_delta=on_delta
        )
        last = msg
        messages.append(msg.to_wire())
        if not msg.tool_calls:
            return msg

        for tc in msg.tool_calls:
            tool = active.get(tc.name)
            try:
                args = json.loads(tc.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if on_tool_event:
                on_tool_event("tool_start", {"name": tc.name, "args": args})

            if (
                tool is not None
                and tool.needs_approval
                and approve is not None
                and not approve(tool, args)
            ):
                result = ToolResult("Tool call denied by user", is_error=True)
                _emit_end(on_tool_event, tc.name, result)
                messages.append(_tool_wire(tc, result))
                continue

            result = run_tool(active, tc.name, tc.arguments)
            _emit_end(on_tool_event, tc.name, result)
            messages.append(_tool_wire(tc, result))

    last.content = last.content or "\n\n[stopped: max tool rounds reached]"
    return last


def _tool_wire(tc, result: ToolResult) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tc.id,
        "name": tc.name,
        "content": result.content,
        "is_error": result.is_error,
    }


def _emit_end(cb, name: str, result: ToolResult) -> None:
    if cb:
        cb(
            "tool_end",
            {"name": name, "is_error": result.is_error, "preview": result.content[:400]},
        )
