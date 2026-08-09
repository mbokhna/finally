from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class PriceUpdate:
    symbol: str
    price: float
    previous_price: float | None
    timestamp: datetime

    @property
    def change(self) -> float | None:
        if self.previous_price is None:
            return None
        return self.price - self.previous_price

    @property
    def direction(self) -> Literal["up", "down", "flat"]:
        if self.previous_price is None or self.price == self.previous_price:
            return "flat"
        return "up" if self.price > self.previous_price else "down"


@dataclass(frozen=True)
class Candle:
    t: datetime
    o: float
    h: float
    l: float  # noqa: E741 — mirrors the OHLCV JSON contract in docs/API.md
    c: float
    v: float
