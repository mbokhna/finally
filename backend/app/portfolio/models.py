from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    avg_cost: float


@dataclass(frozen=True)
class Trade:
    id: int
    symbol: str
    side: Side
    quantity: float
    price: float
    executed_at: datetime


@dataclass(frozen=True)
class PositionValuation:
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float | None
    market_value: float | None
    unrealised_pnl: float | None
    unrealised_pnl_pct: float | None


@dataclass(frozen=True)
class PortfolioValuation:
    cash: float
    positions: list[PositionValuation]
    total_value: float
    currency: str
