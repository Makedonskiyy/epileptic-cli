"""Provider-agnostic chat abstractions.

Messages are stored internally in OpenAI wire format and translated per provider:
    {"role": "system"|"user"|"assistant"|"tool", "content": str|None,
     "tool_calls": [...], "tool_call_id": str, "name": str}
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    def to_wire(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in self.tool_calls
            ]
        return msg


@dataclass
class StreamEvent:
    kind: str  # "delta" | "done" | "error"
    text: str = ""
    message: AssistantMessage | None = None
    error: str = ""


ToolSpec = dict[str, Any]  # OpenAI function-tool schema
OnDelta = Callable[[str], None]


class Provider:
    """Base class for chat providers."""

    supports_tools = True

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_delta: OnDelta | None = None,
    ) -> AssistantMessage:
        raise NotImplementedError

    def complete(
        self, messages: list[dict[str, Any]], model: str, max_tokens: int | None = 1024
    ) -> str:
        """Non-streaming single completion (used for /compact summaries etc.)."""
        msg = self.stream_chat(messages, model, tools=None, max_tokens=max_tokens)
        return msg.content

    def list_models(self) -> list[str]:
        return []
