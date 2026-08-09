from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.stream import snapshot_payload, sse_price_events

router = APIRouter()


def _get_cache(request: Request) -> PriceCache:
    return cast(PriceCache, request.app.state.price_cache)


def _get_source(request: Request) -> MarketDataSource:
    return cast(MarketDataSource, request.app.state.market_data_source)


@router.get("/api/prices")
async def get_prices(request: Request) -> dict[str, object]:
    payload, _ = snapshot_payload(_get_cache(request))
    return payload


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    return StreamingResponse(
        sse_price_events(_get_cache(request)), media_type="text/event-stream"
    )


@router.get("/api/candles/{symbol}")
async def get_candles(
    symbol: str, request: Request, interval: str = "1h", limit: int = 200
) -> dict[str, object]:
    candles = await _get_source(request).get_candles(symbol, interval, limit)
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": [
            {"t": candle.t.isoformat(), "o": candle.o, "h": candle.h, "l": candle.l,
             "c": candle.c, "v": candle.v}
            for candle in candles
        ],
    }
