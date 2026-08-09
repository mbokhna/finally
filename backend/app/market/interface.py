from __future__ import annotations

from abc import ABC, abstractmethod

from app.market.models import Candle


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push updates into a shared PriceCache on their own schedule.
    Downstream code never calls a data source directly — it reads the cache.
    """

    @abstractmethod
    async def start(self, symbols: list[str]) -> None:
        """Begin producing updates. Called exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop and release resources. Idempotent."""

    @abstractmethod
    async def add_symbol(self, symbol: str) -> None:
        """Add to the active set. No-op if present."""

    @abstractmethod
    async def remove_symbol(self, symbol: str) -> None:
        """Remove from the active set and from the cache. No-op if absent."""

    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Currently tracked symbols."""

    @abstractmethod
    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        """Historical candles, newest last. Used by the backtester."""
