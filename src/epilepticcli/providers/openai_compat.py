"""OpenAI-compatible provider.

Covers OpenAI itself plus every endpoint that speaks the /chat/completions
protocol: OpenRouter, DeepSeek, Groq, Together, Mistral, xAI, Gemini's
OpenAI-compat endpoint, Ollama, LM Studio, and any custom reseller base_url.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from epilepticcli.config import ProviderConfig
from epilepticcli.providers.base import (
    AssistantMessage,
    OnDelta,
    Provider,
    ToolCall,
    ToolSpec,
    Usage,
)


class OpenAICompatProvider(Provider):
    def __init__(self, cfg: ProviderConfig, env_key: str | None = None) -> None:
        self.cfg = cfg
        self.client = OpenAI(
            base_url=cfg.base_url,
            api_key=cfg.resolved_api_key(env_key) or "not-required",
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
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        content_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        usage = Usage()

        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.usage:
                usage.input_tokens = chunk.usage.prompt_tokens or 0
                usage.output_tokens = chunk.usage.completion_tokens or 0
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
                if on_delta:
                    on_delta(delta.content)
            for tc in delta.tool_calls or []:
                slot = calls.setdefault(
                    tc.index, {"id": "", "name": "", "args": []}
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function.arguments:
                        slot["args"].append(tc.function.arguments)

        tool_calls = [
            ToolCall(
                id=c["id"] or f"call_{i}",
                name=c["name"],
                arguments="".join(c["args"]),
            )
            for i, c in sorted(calls.items())
        ]
        return AssistantMessage(
            content="".join(content_parts), tool_calls=tool_calls, usage=usage
        )

    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except Exception:
            return []
