from __future__ import annotations

import pytest

from app.config import get_settings
from app.market.cache import PriceCache
from app.market.composite import CompositeDataSource
from app.market.interface import MarketDataSource
from app.market.models import Candle


class RecordingSource(MarketDataSource):
    """A minimal fake child source, just to observe how the composite drives it."""

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache
        self.started_with: list[str] | None = None
        self.stopped = False
        self._symbols: list[str] = []

    async def start(self, symbols: list[str]) -> None:
        self.started_with = list(symbols)
        self._symbols = list(symbols)

    async def stop(self) -> None:
        self.stopped = True

    async def add_symbol(self, symbol: str) -> None:
        if symbol not in self._symbols:
            self._symbols.append(symbol)

    async def remove_symbol(self, symbol: str) -> None:
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            self._cache.remove(symbol)

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        return []


@pytest.fixture(autouse=True)
def _patch_children(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.market.composite as composite_module

    monkeypatch.setitem(composite_module.PREFIX_MAP, "CRYPTO", RecordingSource)
    monkeypatch.setitem(composite_module.PREFIX_MAP, "GPW", RecordingSource)


def _recording(source: MarketDataSource) -> RecordingSource:
    assert isinstance(source, RecordingSource)
    return source


async def test_start_partitions_symbols_by_prefix() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())

    await composite.start(["CRYPTO:BTCUSDT", "GPW:PKN", "CRYPTO:ETHUSDT"])

    crypto_child = _recording(composite._children["CRYPTO"])
    gpw_child = _recording(composite._children["GPW"])
    assert sorted(crypto_child.started_with or []) == ["CRYPTO:BTCUSDT", "CRYPTO:ETHUSDT"]
    assert gpw_child.started_with == ["GPW:PKN"]


async def test_add_symbol_starts_a_new_child_lazily() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())
    await composite.start(["CRYPTO:BTCUSDT"])

    await composite.add_symbol("GPW:PKN")

    gpw_child = _recording(composite._children["GPW"])
    assert gpw_child.started_with == ["GPW:PKN"]


async def test_add_symbol_routes_to_already_started_child() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())
    await composite.start(["CRYPTO:BTCUSDT"])

    await composite.add_symbol("CRYPTO:ETHUSDT")

    crypto_child = _recording(composite._children["CRYPTO"])
    assert "CRYPTO:ETHUSDT" in crypto_child.get_symbols()


async def test_stop_stops_every_started_child() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())
    await composite.start(["CRYPTO:BTCUSDT", "GPW:PKN"])

    await composite.stop()

    assert _recording(composite._children["CRYPTO"]).stopped
    assert _recording(composite._children["GPW"]).stopped


async def test_unknown_prefix_raises_value_error() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())

    with pytest.raises(ValueError, match="NASDAQ"):
        await composite.start(["NASDAQ:AAPL"])


async def test_get_symbols_aggregates_all_children() -> None:
    cache = PriceCache()
    composite = CompositeDataSource(cache, get_settings())
    await composite.start(["CRYPTO:BTCUSDT", "GPW:PKN"])

    assert sorted(composite.get_symbols()) == ["CRYPTO:BTCUSDT", "GPW:PKN"]
