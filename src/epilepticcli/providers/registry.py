"""Provider presets and resolution.

Any entry in config.yaml `providers:` overrides or extends these presets.
Every preset with type=openai also fits resellers: point `base_url` anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from epilepticcli.config import Config, ProviderConfig
from epilepticcli.providers.anthropic import AnthropicProvider
from epilepticcli.providers.base import Provider
from epilepticcli.providers.demo import DemoProvider
from epilepticcli.providers.openai_compat import OpenAICompatProvider


@dataclass
class Preset:
    type: str
    base_url: str | None = None
    env_key: str | None = None
    models: list[str] = field(default_factory=list)


PRESETS: dict[str, Preset] = {
    "demo": Preset(type="demo", models=["demo"]),
    "openai": Preset(
        type="openai",
        base_url="https://api.openai.com/v1",
        env_key="OPENAI_API_KEY",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini", "o3"],
    ),
    "anthropic": Preset(
        type="anthropic",
        base_url=None,
        env_key="ANTHROPIC_API_KEY",
        models=[
            "claude-opus-4-1",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-sonnet-4-0",
        ],
    ),
    "gemini": Preset(
        type="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        env_key="GEMINI_API_KEY",
        models=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
    ),
    "openrouter": Preset(
        type="openai",
        base_url="https://openrouter.ai/api/v1",
        env_key="OPENROUTER_API_KEY",
        models=[],
    ),
    "deepseek": Preset(
        type="openai",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
        models=["deepseek-chat", "deepseek-reasoner"],
    ),
    "groq": Preset(
        type="openai",
        base_url="https://api.groq.com/openai/v1",
        env_key="GROQ_API_KEY",
        models=["llama-3.3-70b-versatile", "openai/gpt-oss-120b"],
    ),
    "together": Preset(
        type="openai",
        base_url="https://api.together.xyz/v1",
        env_key="TOGETHER_API_KEY",
        models=["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
    ),
    "mistral": Preset(
        type="openai",
        base_url="https://api.mistral.ai/v1",
        env_key="MISTRAL_API_KEY",
        models=["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
    ),
    "xai": Preset(
        type="openai",
        base_url="https://api.x.ai/v1",
        env_key="XAI_API_KEY",
        models=["grok-4", "grok-3", "grok-3-mini"],
    ),
    "selora": Preset(
        type="openai",
        base_url="https://api.selora.lol/v1",
        env_key="SELORA_API_KEY",
        models=["claude-sonnet-5", "kimi-k3"],
    ),
    "selora-anthropic": Preset(
        type="anthropic",
        # bare origin on purpose - the SDK appends /v1/messages itself
        base_url="https://api.selora.lol",
        env_key="SELORA_API_KEY",
        models=["claude-sonnet-5", "kimi-k3"],
    ),
    "darkapi": Preset(
        type="openai",
        base_url="https://darkapi.shop/v1",
        env_key="DARKAPI_API_KEY",
        models=["gpt-6-luna"],
    ),
    "ollama": Preset(
        type="openai",
        base_url="http://localhost:11434/v1",
        env_key=None,
        models=[],
    ),
    "lmstudio": Preset(
        type="openai",
        base_url="http://localhost:1234/v1",
        env_key=None,
        models=[],
    ),
}


def resolve_provider_config(cfg: Config, name: str) -> ProviderConfig:
    """Merge a config entry over its preset (or create a bare custom entry)."""
    preset = PRESETS.get(name)
    user = cfg.providers.get(name)
    if user is None and preset is None:
        raise KeyError(f"Unknown provider '{name}'. Define it in config.yaml or pick a preset.")
    merged = ProviderConfig(
        name=name,
        type=(user.type if user else preset.type),  # type: ignore[union-attr]
        base_url=(user.base_url if user and user.base_url else (preset.base_url if preset else None)),
        api_key=(user.api_key if user else None),
        default_headers=(user.default_headers if user else {}),
        models=(user.models if user and user.models else (preset.models if preset else [])),
    )
    return merged


def resolve_env_key(name: str) -> str | None:
    preset = PRESETS.get(name)
    return preset.env_key if preset else None


def build_provider(cfg: Config, name: str) -> Provider:
    pc = resolve_provider_config(cfg, name)
    env_key = resolve_env_key(name)
    if pc.type == "anthropic":
        return AnthropicProvider(pc, env_key)
    if pc.type == "demo":
        return DemoProvider()
    return OpenAICompatProvider(pc, env_key)


def known_providers(cfg: Config) -> list[str]:
    names = set(PRESETS) | set(cfg.providers)
    return sorted(names)
