from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.market import stream_prices
from app.main import DEFAULT_WATCHLIST, app
from app.market.cache import PriceCache


def test_get_prices_returns_seeded_watchlist() -> None:
    with TestClient(app) as client:
        response = client.get("/api/prices")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["version"], int)
    symbols = {p["symbol"] for p in body["prices"]}
    assert symbols == set(DEFAULT_WATCHLIST)


class _FakeApp:
    def __init__(self, cache: PriceCache) -> None:
        self.state = _FakeState(cache)


class _FakeState:
    def __init__(self, cache: PriceCache) -> None:
        self.price_cache = cache


class _FakeRequest:
    def __init__(self, cache: PriceCache) -> None:
        self.app = _FakeApp(cache)


async def test_stream_prices_wires_cache_into_sse_generator() -> None:
    # The SSE stream never terminates, so httpx's TestClient (which buffers a full
    # ASGI response before returning) hangs on it. Exercise the route function and
    # its body_iterator directly instead of going through a real HTTP round trip.
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    request = cast(Request, _FakeRequest(cache))

    response = await stream_prices(request)

    assert response.media_type == "text/event-stream"
    first_chunk = await anext(response.body_iterator)

    assert isinstance(first_chunk, str)
    assert first_chunk.startswith("data: ")
    assert "CRYPTO:BTCUSDT" in first_chunk
    assert '"version"' in first_chunk
