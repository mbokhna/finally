from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import httpx
import pytest

from app.market.binance import BinanceDataSource
from app.market.cache import PriceCache

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "binance"


class FakeConnection:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []
        self.closed_after_exhausted = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if self._messages:
            return self._messages.pop(0)
        # Idle connection: block until the caller cancels us, like a real socket
        # with nothing new to say.
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class FakeConnect:
    """Matches the `connect(url) -> async context manager` shape BinanceDataSource expects."""

    def __init__(self, messages: list[str] | None = None, fail_times: int = 0) -> None:
        self._messages = messages or []
        self._fail_times = fail_times
        self.urls: list[str] = []
        self.connections: list[FakeConnection] = []

    def __call__(self, url: str) -> FakeConnect:
        self.urls.append(url)
        return self

    async def __aenter__(self) -> FakeConnection:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ConnectionError("simulated connect failure")
        conn = FakeConnection(list(self._messages))
        self.connections.append(conn)
        return conn

    async def __aexit__(self, *exc: object) -> None:
        return None


def _trade_message(rest_symbol: str, price: str) -> str:
    return json.dumps(
        {
            "stream": f"{rest_symbol.lower()}@trade",
            "data": {"e": "trade", "s": rest_symbol, "p": price},
        }
    )


async def _wait_until(predicate: object, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():  # type: ignore[operator]
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


async def test_trade_message_is_written_to_cache() -> None:
    cache = PriceCache()
    connect = FakeConnect(messages=[_trade_message("BTCUSDT", "79000.12")])
    source = BinanceDataSource(cache, connect=connect)

    await source.start(["CRYPTO:BTCUSDT"])
    await _wait_until(lambda: cache.get("CRYPTO:BTCUSDT") is not None)

    update = cache.get("CRYPTO:BTCUSDT")
    assert update is not None
    assert update.price == 79000.12

    await source.stop()


async def test_message_for_untracked_symbol_is_ignored() -> None:
    cache = PriceCache()
    connect = FakeConnect(messages=[_trade_message("ETHUSDT", "3000.0")])
    source = BinanceDataSource(cache, connect=connect)

    await source.start(["CRYPTO:BTCUSDT"])
    await asyncio.sleep(0.05)

    assert cache.get("CRYPTO:ETHUSDT") is None
    await source.stop()


async def test_non_trade_event_is_ignored() -> None:
    cache = PriceCache()
    message = json.dumps({"stream": "btcusdt@depth", "data": {"e": "depthUpdate"}})
    connect = FakeConnect(messages=[message])
    source = BinanceDataSource(cache, connect=connect)

    await source.start(["CRYPTO:BTCUSDT"])
    await asyncio.sleep(0.05)

    assert cache.get("CRYPTO:BTCUSDT") is None
    await source.stop()


async def test_malformed_json_does_not_crash() -> None:
    cache = PriceCache()
    connect = FakeConnect(messages=["not json{{", _trade_message("BTCUSDT", "1.0")])
    source = BinanceDataSource(cache, connect=connect)

    await source.start(["CRYPTO:BTCUSDT"])
    await _wait_until(lambda: cache.get("CRYPTO:BTCUSDT") is not None)

    await source.stop()


async def test_reconnects_after_connect_failure() -> None:
    cache = PriceCache()
    connect = FakeConnect(messages=[_trade_message("BTCUSDT", "50000.0")], fail_times=2)
    source = BinanceDataSource(cache, connect=connect, backoff_initial=0.01, backoff_max=0.05)

    await source.start(["CRYPTO:BTCUSDT"])
    await _wait_until(lambda: cache.get("CRYPTO:BTCUSDT") is not None, timeout=3.0)

    await source.stop()


async def test_remove_symbol_sends_unsubscribe_while_connected() -> None:
    cache = PriceCache()
    connect = FakeConnect(messages=[])
    source = BinanceDataSource(cache, connect=connect)

    await source.start(["CRYPTO:BTCUSDT"])
    await _wait_until(lambda: len(connect.connections) == 1)

    await source.remove_symbol("CRYPTO:BTCUSDT")

    sent = connect.connections[0].sent
    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["method"] == "UNSUBSCRIBE"
    assert payload["params"] == ["btcusdt@trade"]

    await source.stop()


async def test_get_candles_parses_klines_fixture() -> None:
    fixture = (FIXTURES / "klines_btcusdt_1h.json").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "1h"
        return httpx.Response(200, content=fixture)

    http_client = httpx.AsyncClient(
        base_url="https://api.binance.com", transport=httpx.MockTransport(handler)
    )
    source = BinanceDataSource(PriceCache(), http_client=http_client)

    candles = await source.get_candles("CRYPTO:BTCUSDT", "1h", 3)

    assert len(candles) == 3
    assert candles[0].o == pytest.approx(35000.00)
    assert candles[-1].c == pytest.approx(35390.10)
    assert candles[0].t < candles[-1].t

    with contextlib.suppress(Exception):
        await http_client.aclose()
