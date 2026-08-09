from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

MarketMode = Literal["simulator", "live"]


@dataclass(frozen=True)
class Settings:
    market_mode: MarketMode
    currency: str
    db_path: str
    stooq_interval: int
    seed: int
    openrouter_api_key: str | None
    ai_model: str
    ai_max_tokens: int


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _parse_market_mode(value: str) -> MarketMode:
    if value == "simulator":
        return "simulator"
    if value == "live":
        return "live"
    raise ValueError(f"PULSEDESK_MARKET_MODE must be 'simulator' or 'live', got {value!r}")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        market_mode=_parse_market_mode(_env("PULSEDESK_MARKET_MODE", "simulator")),
        currency=_env("PULSEDESK_CURRENCY", "PLN"),
        db_path=_env("PULSEDESK_DB_PATH", "/data/pulsedesk.db"),
        stooq_interval=int(_env("PULSEDESK_STOOQ_INTERVAL", "60")),
        seed=int(_env("PULSEDESK_SEED", "42")),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
        ai_model=_env("PULSEDESK_AI_MODEL", "some-provider/some-model:free"),
        ai_max_tokens=int(_env("PULSEDESK_AI_MAX_TOKENS", "800")),
    )
