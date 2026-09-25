"""Configuration loading for EpilepticCLI.

Config lives in ~/.epilepticcli/ on every OS (same convention as ~/.claude):
    config.yaml        - main config
    agents/*.md        - agent definitions (markdown + YAML frontmatter)
    sessions/*.jsonl   - saved sessions
    history            - prompt input history
    system_prompt.md   - optional custom system prompt override
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path.home() / ".epilepticcli"
CONFIG_FILE = APP_DIR / "config.yaml"
AGENTS_DIR = APP_DIR / "agents"
SESSIONS_DIR = APP_DIR / "sessions"
HISTORY_FILE = APP_DIR / "history"
SYSTEM_PROMPT_FILE = APP_DIR / "system_prompt.md"

DEFAULT_CONFIG: dict[str, Any] = {
    "default_provider": "openai",
    "default_model": "gpt-4o",
    "permission_mode": "ask",  # ask | auto
    "builtin_system_prompt": True,
    "max_tool_rounds": 40,
    "providers": [],
}


@dataclass
class ProviderConfig:
    name: str
    type: str = "openai"  # openai | anthropic | demo
    base_url: str | None = None
    api_key: str | None = None  # literal, "$ENV_VAR", or None
    default_headers: dict[str, str] = field(default_factory=dict)
    models: list[str] = field(default_factory=list)

    def resolved_api_key(self, env_fallback: str | None = None) -> str | None:
        key = self.api_key
        if key and key.startswith("$"):
            return os.environ.get(key[1:])
        if key:
            return key
        if env_fallback:
            return os.environ.get(env_fallback)
        return None


@dataclass
class Config:
    raw: dict[str, Any]
    default_provider: str = "openai"
    default_model: str = "gpt-4o"
    permission_mode: str = "ask"
    builtin_system_prompt: bool = True
    max_tool_rounds: int = 40
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    def provider(self, name: str | None = None) -> ProviderConfig | None:
        return self.providers.get(name or self.default_provider)


def ensure_dirs() -> None:
    for d in (APP_DIR, AGENTS_DIR, SESSIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    ensure_dirs()
    raw: dict[str, Any] = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            user = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            if isinstance(user, dict):
                raw.update(user)
        except yaml.YAMLError:
            pass

    providers: dict[str, ProviderConfig] = {}
    for entry in raw.get("providers") or []:
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        pc = ProviderConfig(
            name=str(entry["name"]),
            type=str(entry.get("type", "openai")),
            base_url=entry.get("base_url"),
            api_key=entry.get("api_key"),
            default_headers=dict(entry.get("default_headers") or {}),
            models=list(entry.get("models") or []),
        )
        providers[pc.name] = pc

    return Config(
        raw=raw,
        default_provider=str(raw.get("default_provider") or "openai"),
        default_model=str(raw.get("default_model") or "gpt-4o"),
        permission_mode=str(raw.get("permission_mode") or "ask"),
        builtin_system_prompt=bool(raw.get("builtin_system_prompt", True)),
        max_tool_rounds=int(raw.get("max_tool_rounds") or 40),
        providers=providers,
    )


def ensure_provider_entry(cfg: Config, name: str) -> ProviderConfig:
    """Return the config entry for `name`, creating it from preset defaults.

    Copies the preset's fields so saving the entry preserves type/base_url —
    a bare {name, api_key} entry would otherwise silently reset type to openai.
    """
    if name in cfg.providers:
        return cfg.providers[name]
    from epilepticcli.providers.registry import PRESETS

    preset = PRESETS.get(name)
    pc = ProviderConfig(
        name=name,
        type=preset.type if preset else "openai",
        base_url=preset.base_url if preset else None,
        models=list(preset.models) if preset else [],
    )
    cfg.providers[name] = pc
    return pc


def provider_has_key(cfg: Config, name: str) -> bool:
    """True if the provider has a usable key (stored or via env var)."""
    from epilepticcli.providers.registry import resolve_env_key, resolve_provider_config

    try:
        pc = resolve_provider_config(cfg, name)
    except KeyError:
        return False
    env_key = resolve_env_key(name)
    if env_key is None:
        return True  # keyless provider (ollama, lmstudio, demo)
    return pc.resolved_api_key(env_key) is not None


def save_config(cfg: Config) -> None:
    ensure_dirs()
    data = {
        "default_provider": cfg.default_provider,
        "default_model": cfg.default_model,
        "permission_mode": cfg.permission_mode,
        "builtin_system_prompt": cfg.builtin_system_prompt,
        "max_tool_rounds": cfg.max_tool_rounds,
        "providers": [
            {
                "name": p.name,
                "type": p.type,
                **({"base_url": p.base_url} if p.base_url else {}),
                **({"api_key": p.api_key} if p.api_key else {}),
                **({"default_headers": p.default_headers} if p.default_headers else {}),
                **({"models": p.models} if p.models else {}),
            }
            for p in cfg.providers.values()
        ],
    }
    CONFIG_FILE.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
