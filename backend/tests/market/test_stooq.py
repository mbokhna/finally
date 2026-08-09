from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import httpx
import pytest

from app.market.cache import PriceCache
from app.market.stooq import StooqDataSource, _parse_daily_csv, _parse_quote_csv

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stooq"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_quote_csv_reads_close_price() -> None:
    assert _parse_quote_csv(_read("quote_pkn.csv")) == pytest.approx(65.20)


def test_parse_quote_csv_handles_nd() -> None:
    assert _parse_quote_csv(_read("quote_nd.csv")) is None


def test_parse_quote_csv_handles_unexpected_html() -> None:
    # This is what the live /q/l/ endpoint actually returns today — an error
    # page, not a 404 status. Degrade gracefully rather than crashing.
    assert _parse_quote_csv(_read("not_found.html")) is None


def test_parse_daily_csv_is_newest_last() -> None:
    candles = _parse_daily_csv(_read("daily_pkn.csv"))

    assert len(candles) == 4
    assert candles[0].t < candles[-1].t
    assert candles[-1].c == pytest.approx(65.20)


def test_parse_daily_csv_handles_garbage() -> None:
    assert _parse_daily_csv("<html>not csv</html>") == []


async def _wait_until(predicate: object, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():  # type: ignore[operator]
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def _client_returning(text: str) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=text)

    return httpx.AsyncClient(base_url="https://stooq.pl", transport=httpx.MockTransport(handler))


async def test_poll_writes_price_to_cache() -> None:
    cache = PriceCache()
    http_client = _client_returning(_read("quote_pkn.csv"))
    source = StooqDataSource(cache, http_client=http_client, poll_seconds=0.01)

    await source.start(["GPW:PKN"])
    await _wait_until(lambda: cache.get("GPW:PKN") is not None)

    update = cache.get("GPW:PKN")
    assert update is not None
    assert update.price == pytest.approx(65.20)

    await source.stop()


async def test_poll_skips_nd_without_crashing() -> None:
    cache = PriceCache()
    http_client = _client_returning(_read("quote_nd.csv"))
    source = StooqDataSource(cache, http_client=http_client, poll_seconds=0.01)

    await source.start(["GPW:PKN"])
    await asyncio.sleep(0.05)

    assert cache.get("GPW:PKN") is None
    await source.stop()


async def test_get_candles_respects_limit() -> None:
    http_client = _client_returning(_read("daily_pkn.csv"))
    source = StooqDataSource(PriceCache(), http_client=http_client)

    candles = await source.get_candles("GPW:PKN", "d", 2)

    assert len(candles) == 2
    assert candles[-1].c == pytest.approx(65.20)

    with contextlib.suppress(Exception):
        await http_client.aclose()


async def test_get_candles_returns_empty_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    http_client = httpx.AsyncClient(
        base_url="https://stooq.pl", transport=httpx.MockTransport(handler)
    )
    source = StooqDataSource(PriceCache(), http_client=http_client)

    candles = await source.get_candles("GPW:PKN", "d", 10)

    assert candles == []
    with contextlib.suppress(Exception):
        await http_client.aclose()
