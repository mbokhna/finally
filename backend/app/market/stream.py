from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.market.cache import PriceCache
from app.market.models import PriceUpdate

POLL_SECONDS = 0.1
HEARTBEAT_SECONDS = 15.0


def serialize_update(update: PriceUpdate) -> dict[str, object]:
    return {
        "symbol": update.symbol,
        "price": update.price,
        "previous_price": update.previous_price,
        "change": update.change,
        "direction": update.direction,
        "timestamp": update.timestamp.isoformat(),
    }


def snapshot_payload(cache: PriceCache) -> tuple[dict[str, object], int]:
    snapshot, version = cache.snapshot()
    payload: dict[str, object] = {
        "prices": [serialize_update(update) for update in snapshot],
        "version": version,
    }
    return payload, version


async def sse_price_events(
    cache: PriceCache,
    *,
    poll_seconds: float = POLL_SECONDS,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Emit a frame only when the cache version moves; heartbeat otherwise.

    Outside GPW trading hours nothing changes for hours — re-sending the
    snapshot on a timer would spam identical frames for no reason.
    """
    loop = asyncio.get_running_loop()
    last_seen = -1
    last_emit = loop.time()
    while True:
        payload, version = snapshot_payload(cache)
        if version != last_seen:
            yield f"data: {json.dumps(payload)}\n\n"
            last_seen = version
            last_emit = loop.time()
        elif loop.time() - last_emit >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_emit = loop.time()
        await asyncio.sleep(poll_seconds)
