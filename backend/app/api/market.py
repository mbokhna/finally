from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.market.cache import PriceCache
from app.market.stream import snapshot_payload, sse_price_events

router = APIRouter()


def _get_cache(request: Request) -> PriceCache:
    return cast(PriceCache, request.app.state.price_cache)


@router.get("/api/prices")
async def get_prices(request: Request) -> dict[str, object]:
    payload, _ = snapshot_payload(_get_cache(request))
    return payload


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    return StreamingResponse(
        sse_price_events(_get_cache(request)), media_type="text/event-stream"
    )
