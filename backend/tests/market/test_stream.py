from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

from app.market.cache import PriceCache
from app.market.stream import snapshot_payload, sse_price_events


async def test_snapshot_payload_reflects_cache() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))

    payload, version = snapshot_payload(cache)

    assert payload["version"] == version
    prices = payload["prices"]
    assert isinstance(prices, list)
    assert prices[0]["symbol"] == "CRYPTO:BTCUSDT"
    assert prices[0]["price"] == 100.0


async def test_stream_emits_immediately_for_existing_snapshot() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    events = sse_price_events(cache, poll_seconds=0.01, heartbeat_seconds=100.0)

    first = await anext(events)

    assert first.startswith("data: ")
    assert "CRYPTO:BTCUSDT" in first


async def test_stream_stays_quiet_without_change_or_heartbeat() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    events = sse_price_events(cache, poll_seconds=0.01, heartbeat_seconds=100.0)
    await anext(events)

    task = asyncio.ensure_future(anext(events))
    done, _ = await asyncio.wait({task}, timeout=0.05)

    assert not done
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_stream_emits_heartbeat_when_idle() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    events = sse_price_events(cache, poll_seconds=0.01, heartbeat_seconds=0.02)
    await anext(events)

    second = await anext(events)

    assert second == ": heartbeat\n\n"


async def test_stream_emits_new_snapshot_on_price_change() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    events = sse_price_events(cache, poll_seconds=0.01, heartbeat_seconds=100.0)
    await anext(events)

    cache.write("CRYPTO:BTCUSDT", 105.0, datetime.now(UTC))
    second = await anext(events)

    assert "105.0" in second
