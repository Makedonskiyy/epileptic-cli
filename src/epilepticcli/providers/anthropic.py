"""Native Anthropic Messages API provider."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from epilepticcli.config import ProviderConfig
from epilepticcli.providers.base import (
    AssistantMessage,
    OnDelta,
    Provider,
    ToolCall,
    ToolSpec,
    Usage,
)


def _convert_tools(tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return out


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            if msg.get("content"):
                system_parts.append(str(msg["content"]))
            continue
        if role == "user":
            out.append({"role": "user", "content": msg.get("content") or ""})
            continue
        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": fn.get("arguments", "")}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": args,
                    }
                )
            out.append({"role": "assistant", "content": blocks or ""})
            continue
        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": str(msg.get("content") or ""),
                "is_error": bool(msg.get("is_error")),
            }
            # Anthropic requires tool_result blocks inside a user message; merge
            # consecutive results into the last user message.
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
            continue

    return ("\n\n".join(system_parts) or None), out


class AnthropicProvider(Provider):
    def __init__(self, cfg: ProviderConfig, env_key: str | None = None) -> None:
        self.cfg = cfg
        self.client = anthropic.Anthropic(
            api_key=cfg.resolved_api_key(env_key) or "not-required",
            base_url=cfg.base_url,
            default_headers=cfg.default_headers or None,
        )

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_delta: OnDelta | None = None,
    ) -> AssistantMessage:
        system, msgs = _convert_messages(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens or 8192,
        }
        if system:
            kwargs["system"] = system
        converted = _convert_tools(tools)
        if converted:
            kwargs["tools"] = converted
        if temperature is not None:
            kwargs["temperature"] = temperature

        content_parts: list[str] = []
        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                content_parts.append(text)
                if on_delta:
                    on_delta(text)
            final = stream.get_final_message()

        tool_calls = [
            ToolCall(id=b.id, name=b.name, arguments=json.dumps(b.input))
            for b in final.content
            if getattr(b, "type", None) == "tool_use"
        ]
        usage = Usage(
            input_tokens=getattr(final.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(final.usage, "output_tokens", 0) or 0,
        )
        return AssistantMessage(
            content="".join(content_parts), tool_calls=tool_calls, usage=usage
        )
