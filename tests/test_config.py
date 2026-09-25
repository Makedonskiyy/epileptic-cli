
from epilepticcli.config import ProviderConfig


def test_api_key_env_resolution(monkeypatch):
    monkeypatch.setenv("EPI_TEST_KEY", "sk-secret")
    assert ProviderConfig(name="x", api_key="$EPI_TEST_KEY").resolved_api_key() == "sk-secret"


def test_api_key_literal():
    assert ProviderConfig(name="x", api_key="sk-lit").resolved_api_key() == "sk-lit"


def test_api_key_fallback(monkeypatch):
    monkeypatch.setenv("EPI_FALLBACK", "sk-fb")
    assert ProviderConfig(name="x").resolved_api_key("EPI_FALLBACK") == "sk-fb"
    assert ProviderConfig(name="x").resolved_api_key() is None
