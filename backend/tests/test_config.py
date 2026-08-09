from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "PULSEDESK_MARKET_MODE",
        "PULSEDESK_CURRENCY",
        "PULSEDESK_DB_PATH",
        "PULSEDESK_STOOQ_INTERVAL",
        "PULSEDESK_SEED",
        "OPENROUTER_API_KEY",
        "PULSEDESK_AI_MODEL",
        "PULSEDESK_AI_MAX_TOKENS",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = get_settings()

    assert settings.market_mode == "simulator"
    assert settings.currency == "PLN"
    assert settings.db_path == "/data/pulsedesk.db"
    assert settings.stooq_interval == 60
    assert settings.seed == 42
    assert settings.openrouter_api_key is None
    assert settings.ai_model == "some-provider/some-model:free"
    assert settings.ai_max_tokens == 800


def test_reads_overrides_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSEDESK_MARKET_MODE", "live")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

    settings = get_settings()

    assert settings.market_mode == "live"
    assert settings.openrouter_api_key == "sk-or-v1-test"


def test_invalid_market_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSEDESK_MARKET_MODE", "nonsense")

    with pytest.raises(ValueError, match="PULSEDESK_MARKET_MODE"):
        get_settings()
