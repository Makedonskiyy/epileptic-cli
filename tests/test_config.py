
from epilepticcli.config import (
    Config,
    ProviderConfig,
    ensure_provider_entry,
    provider_has_key,
)


def test_api_key_env_resolution(monkeypatch):
    monkeypatch.setenv("EPI_TEST_KEY", "sk-secret")
    assert ProviderConfig(name="x", api_key="$EPI_TEST_KEY").resolved_api_key() == "sk-secret"


def test_api_key_literal():
    assert ProviderConfig(name="x", api_key="sk-lit").resolved_api_key() == "sk-lit"


def test_api_key_fallback(monkeypatch):
    monkeypatch.setenv("EPI_FALLBACK", "sk-fb")
    assert ProviderConfig(name="x").resolved_api_key("EPI_FALLBACK") == "sk-fb"
    assert ProviderConfig(name="x").resolved_api_key() is None


def test_ensure_provider_entry_copies_preset():
    """A saved entry for a preset must keep its type/base_url (esp. non-openai)."""
    cfg = Config(raw={})
    pc = ensure_provider_entry(cfg, "selora-anthropic")
    assert pc.type == "anthropic"
    assert pc.base_url == "https://api.selora.lol"
    pc = ensure_provider_entry(cfg, "selora")
    assert pc.type == "openai"
    assert pc.base_url == "https://api.selora.lol/v1"
    # unknown provider defaults to openai
    pc = ensure_provider_entry(cfg, "custom-gw")
    assert pc.type == "openai"


def test_provider_has_key(monkeypatch):
    cfg = Config(raw={})
    assert provider_has_key(cfg, "openai") is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert provider_has_key(cfg, "openai") is True
    monkeypatch.delenv("OPENAI_API_KEY")
    cfg.providers["openai"] = ProviderConfig(name="openai", type="openai", api_key="sk-cfg")
    assert provider_has_key(cfg, "openai") is True
    assert provider_has_key(cfg, "demo") is True  # keyless
