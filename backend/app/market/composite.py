from __future__ import annotations

from collections.abc import Callable

from app.config import Settings
from app.market.binance import BinanceDataSource
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.models import Candle
from app.market.stooq import StooqDataSource

PREFIX_MAP: dict[str, Callable[[PriceCache], MarketDataSource]] = {
    "CRYPTO": BinanceDataSource,
    "GPW": StooqDataSource,
}


def _prefix(symbol: str) -> str:
    return symbol.split(":", 1)[0]


class CompositeDataSource(MarketDataSource):
    """Routes by symbol prefix to one child source per market.

    In simulator mode this class is bypassed entirely — see factory.py.
    """

    def __init__(self, cache: PriceCache, settings: Settings) -> None:
        self._cache = cache
        self._settings = settings
        self._children: dict[str, MarketDataSource] = {}
        self._started: set[str] = set()

    async def start(self, symbols: list[str]) -> None:
        by_prefix: dict[str, list[str]] = {}
        for symbol in symbols:
            by_prefix.setdefault(_prefix(symbol), []).append(symbol)
        for prefix, prefix_symbols in by_prefix.items():
            await self._child_for_prefix(prefix).start(prefix_symbols)
            self._started.add(prefix)

    async def stop(self) -> None:
        for prefix in list(self._started):
            await self._children[prefix].stop()
        self._started.clear()

    async def add_symbol(self, symbol: str) -> None:
        prefix = _prefix(symbol)
        child = self._child_for_prefix(prefix)
        if prefix not in self._started:
            await child.start([symbol])
            self._started.add(prefix)
        else:
            await child.add_symbol(symbol)

    async def remove_symbol(self, symbol: str) -> None:
        child = self._children.get(_prefix(symbol))
        if child is not None:
            await child.remove_symbol(symbol)

    def get_symbols(self) -> list[str]:
        symbols: list[str] = []
        for child in self._children.values():
            symbols.extend(child.get_symbols())
        return symbols

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        return await self._child_for_prefix(_prefix(symbol)).get_candles(symbol, interval, limit)

    def _child_for_prefix(self, prefix: str) -> MarketDataSource:
        child = self._children.get(prefix)
        if child is not None:
            return child
        source_factory = PREFIX_MAP.get(prefix)
        if source_factory is None:
            raise ValueError(f"No data source registered for prefix {prefix!r}")
        if source_factory is StooqDataSource:
            child = StooqDataSource(
                self._cache, poll_seconds=float(self._settings.stooq_interval)
            )
        else:
            child = source_factory(self._cache)
        self._children[prefix] = child
        return child
