from __future__ import annotations

import threading
from datetime import datetime

from app.market.models import PriceUpdate


class PriceCache:
    """Single source of truth for prices. Producers write, consumers read.

    A version counter lets consumers (SSE) skip re-emitting when nothing moved.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prices: dict[str, PriceUpdate] = {}
        self._version = 0

    def write(self, symbol: str, price: float, timestamp: datetime) -> PriceUpdate:
        with self._lock:
            previous = self._prices.get(symbol)
            update = PriceUpdate(
                symbol=symbol,
                price=price,
                previous_price=previous.price if previous is not None else None,
                timestamp=timestamp,
            )
            self._prices[symbol] = update
            self._version += 1
            return update

    def remove(self, symbol: str) -> None:
        with self._lock:
            if symbol in self._prices:
                del self._prices[symbol]
                self._version += 1

    def get(self, symbol: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(symbol)

    def snapshot(self) -> tuple[list[PriceUpdate], int]:
        with self._lock:
            return list(self._prices.values()), self._version
