from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import httpx
import websockets

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.models import Candle

BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"
BINANCE_REST_BASE = "https://api.binance.com"
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 30.0


class WSConnection(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str: ...


WSConnect = Callable[[str], AbstractAsyncContextManager[WSConnection]]


def _default_connect(url: str) -> AbstractAsyncContextManager[WSConnection]:
    # websockets' ClientConnection.recv() returns str | bytes; Binance only ever
    # sends text frames, so narrowing to our str-only Protocol is safe here.
    return cast(AbstractAsyncContextManager[WSConnection], websockets.connect(url))


def _to_stream_symbol(symbol: str) -> str:
    return symbol.split(":", 1)[1].lower()


def _to_rest_symbol(symbol: str) -> str:
    return symbol.split(":", 1)[1].upper()


def _parse_kline(row: Any) -> Candle:
    open_time_ms, open_, high, low, close, volume = row[0], row[1], row[2], row[3], row[4], row[5]
    return Candle(
        t=datetime.fromtimestamp(float(open_time_ms) / 1000, tz=UTC),
        o=float(open_),
        h=float(high),
        l=float(low),
        c=float(close),
        v=float(volume),
    )


class BinanceDataSource(MarketDataSource):
    """Public Binance WebSocket stream, no key required.

    Reconnects with exponential backoff (1s -> 30s cap) — Binance itself closes
    sockets every 24h, so a disconnect is routine, not an error.
    """

    def __init__(
        self,
        cache: PriceCache,
        *,
        connect: WSConnect | None = None,
        http_client: httpx.AsyncClient | None = None,
        backoff_initial: float = BACKOFF_INITIAL,
        backoff_max: float = BACKOFF_MAX,
    ) -> None:
        self._cache = cache
        self._connect = connect or _default_connect
        self._http_client = http_client or httpx.AsyncClient(
            base_url=BINANCE_REST_BASE, timeout=10.0
        )
        self._owns_http_client = http_client is None
        self._backoff_initial = backoff_initial
        self._backoff_max = backoff_max
        self._symbols: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self._conn: WSConnection | None = None
        self._has_symbols = asyncio.Event()

    async def start(self, symbols: list[str]) -> None:
        self._symbols.update(symbols)
        if self._symbols:
            self._has_symbols.set()
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._owns_http_client:
            await self._http_client.aclose()

    async def add_symbol(self, symbol: str) -> None:
        if symbol in self._symbols:
            return
        self._symbols.add(symbol)
        self._has_symbols.set()
        if self._conn is not None:
            await self._send_control(self._conn, "SUBSCRIBE", [symbol])

    async def remove_symbol(self, symbol: str) -> None:
        if symbol not in self._symbols:
            return
        self._symbols.discard(symbol)
        self._cache.remove(symbol)
        if self._conn is not None:
            await self._send_control(self._conn, "UNSUBSCRIBE", [symbol])
        if not self._symbols:
            self._has_symbols.clear()

    def get_symbols(self) -> list[str]:
        return sorted(self._symbols)

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        response = await self._http_client.get(
            "/api/v3/klines",
            params={"symbol": _to_rest_symbol(symbol), "interval": interval, "limit": limit},
        )
        response.raise_for_status()
        return [_parse_kline(row) for row in response.json()]

    async def _run(self) -> None:
        backoff = self._backoff_initial
        while True:
            await self._has_symbols.wait()
            try:
                async with self._connect(self._stream_url()) as conn:
                    self._conn = conn
                    backoff = self._backoff_initial
                    while True:
                        raw = await conn.recv()
                        self._handle_message(raw)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            finally:
                self._conn = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._backoff_max)

    def _stream_url(self) -> str:
        streams = "/".join(f"{_to_stream_symbol(s)}@trade" for s in sorted(self._symbols))
        return f"{BINANCE_WS_BASE}?streams={streams}"

    async def _send_control(self, conn: WSConnection, method: str, symbols: list[str]) -> None:
        params = [f"{_to_stream_symbol(s)}@trade" for s in symbols]
        await conn.send(json.dumps({"method": method, "params": params, "id": 1}))

    def _handle_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or data.get("e") != "trade":
            return
        rest_symbol, price = data.get("s"), data.get("p")
        if not isinstance(rest_symbol, str) or not isinstance(price, str):
            return
        symbol = f"CRYPTO:{rest_symbol.upper()}"
        if symbol not in self._symbols:
            return
        try:
            value = float(price)
        except ValueError:
            return
        self._cache.write(symbol, value, datetime.now(UTC))
