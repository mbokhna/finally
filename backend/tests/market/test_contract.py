from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.market.binance import BinanceDataSource
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.simulator import SimulatorDataSource
from app.market.stooq import StooqDataSource
from tests.market.test_binance import FakeConnect, _trade_message

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _make_simulator(cache: PriceCache) -> MarketDataSource:
    return SimulatorDataSource(cache, seed=42)


def _make_binance(cache: PriceCache) -> MarketDataSource:
    connect = FakeConnect(messages=[_trade_message("BTCUSDT", "79000.12")])
    return BinanceDataSource(cache, connect=connect)


def _make_stooq(cache: PriceCache) -> MarketDataSource:
    fixture = (FIXTURES / "stooq" / "quote_pkn.csv").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    http_client = httpx.AsyncClient(
        base_url="https://stooq.pl", transport=httpx.MockTransport(handler)
    )
    return StooqDataSource(cache, http_client=http_client, poll_seconds=0.01)


CASES: list[tuple[str, Callable[[PriceCache], MarketDataSource], str]] = [
    ("simulator", _make_simulator, "CRYPTO:BTCUSDT"),
    ("binance", _make_binance, "CRYPTO:BTCUSDT"),
    ("stooq", _make_stooq, "GPW:PKN"),
]
CASE_IDS = [case[0] for case in CASES]


async def _wait_for_price(cache: PriceCache, symbol: str, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while cache.get(symbol) is None:
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"no price for {symbol} within {timeout}s")
        await asyncio.sleep(0.01)


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_start_populates_the_cache(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)

    await source.start([symbol])
    await _wait_for_price(cache, symbol)

    assert cache.get(symbol) is not None
    await source.stop()


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_stop_is_idempotent(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)
    await source.start([symbol])

    await source.stop()
    await source.stop()  # must not raise


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_remove_symbol_clears_the_cache_entry(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)
    await source.start([symbol])
    await _wait_for_price(cache, symbol)

    await source.remove_symbol(symbol)

    assert cache.get(symbol) is None
    assert symbol not in source.get_symbols()
    await source.stop()


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_add_symbol_is_idempotent(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)
    await source.start([])

    await source.add_symbol(symbol)
    await source.add_symbol(symbol)  # duplicate — must not crash or double-add

    assert source.get_symbols().count(symbol) == 1
    await source.stop()


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_remove_unknown_symbol_does_not_crash(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)
    await source.start([])

    await source.remove_symbol(symbol)  # never added

    await source.stop()


@pytest.mark.parametrize("name,factory,symbol", CASES, ids=CASE_IDS)
async def test_get_symbols_reflects_current_set(
    name: str, factory: Callable[[PriceCache], MarketDataSource], symbol: str
) -> None:
    cache = PriceCache()
    source = factory(cache)
    await source.start([symbol])

    assert source.get_symbols() == [symbol]

    await source.remove_symbol(symbol)
    assert source.get_symbols() == []

    await source.stop()
