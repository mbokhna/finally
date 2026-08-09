from __future__ import annotations

import asyncio
import contextlib
import csv
import io
from datetime import UTC, datetime

import httpx

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.models import Candle

STOOQ_BASE = "https://stooq.pl"
POLL_SECONDS_DEFAULT = 60.0


def _to_stooq_ticker(symbol: str) -> str:
    return symbol.split(":", 1)[1].lower()


def _parse_quote_csv(text: str) -> float | None:
    """Latest-quote CSV (`f=sd2t2ohlcv`): Symbol,Date,Time,Open,High,Low,Close,Volume.

    Returns None on anything unexpected — "N/D" outside trading hours, an empty
    body, or a non-CSV response (an HTML error page). Best-effort by design: this
    source has no SLA and its endpoints can change without notice.
    """
    try:
        rows = list(csv.reader(io.StringIO(text.strip())))
    except csv.Error:
        return None
    if len(rows) < 2 or len(rows[0]) < 8:
        return None
    header = [h.strip().lower() for h in rows[0]]
    row = dict(zip(header, rows[1], strict=False))
    close = row.get("close")
    if not close or close == "N/D":
        return None
    try:
        return float(close)
    except ValueError:
        return None


def _parse_daily_csv(text: str) -> list[Candle]:
    """Daily-history CSV: Date,Open,High,Low,Close,Volume. Newest last."""
    candles: list[Candle] = []
    try:
        reader = csv.DictReader(io.StringIO(text.strip()))
        for row in reader:
            date = row.get("Date")
            if not date or date == "N/D":
                continue
            candles.append(
                Candle(
                    t=datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC),
                    o=float(row["Open"]),
                    h=float(row["High"]),
                    l=float(row["Low"]),
                    c=float(row["Close"]),
                    v=float(row["Volume"]),
                )
            )
    except (csv.Error, KeyError, ValueError):
        return candles
    return candles


class StooqDataSource(MarketDataSource):
    """Free GPW CSV endpoints, no key. Poll-based — the source itself is

    delayed, so polling faster than `poll_seconds` gains nothing.
    """

    def __init__(
        self,
        cache: PriceCache,
        *,
        http_client: httpx.AsyncClient | None = None,
        poll_seconds: float = POLL_SECONDS_DEFAULT,
    ) -> None:
        self._cache = cache
        self._http_client = http_client or httpx.AsyncClient(base_url=STOOQ_BASE, timeout=10.0)
        self._owns_http_client = http_client is None
        self._poll_seconds = poll_seconds
        self._symbols: list[str] = []
        self._task: asyncio.Task[None] | None = None

    async def start(self, symbols: list[str]) -> None:
        for symbol in symbols:
            if symbol not in self._symbols:
                self._symbols.append(symbol)
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
        if symbol not in self._symbols:
            self._symbols.append(symbol)

    async def remove_symbol(self, symbol: str) -> None:
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            self._cache.remove(symbol)

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        try:
            response = await self._http_client.get(
                "/q/d/l/", params={"s": _to_stooq_ticker(symbol), "i": "d"}
            )
        except httpx.HTTPError:
            return []
        if response.status_code != 200:
            return []
        return _parse_daily_csv(response.text)[-limit:]

    async def _run(self) -> None:
        while True:
            for symbol in list(self._symbols):
                await self._poll_one(symbol)
            await asyncio.sleep(self._poll_seconds)

    async def _poll_one(self, symbol: str) -> None:
        try:
            response = await self._http_client.get(
                "/q/l/",
                params={"s": _to_stooq_ticker(symbol), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            )
        except httpx.HTTPError:
            return
        if response.status_code != 200:
            return
        price = _parse_quote_csv(response.text)
        if price is None:
            return
        self._cache.write(symbol, price, datetime.now(UTC))
