from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.alerts import stream_alerts
from app.main import app


def test_get_alerts_starts_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/alerts")

    assert response.status_code == 200
    assert response.json() == {"alerts": []}


def test_post_alert_creates_it() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/alerts",
            json={"symbol": "CRYPTO:BTCUSDT", "condition": "ABOVE", "threshold": 80000},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["symbol"] == "CRYPTO:BTCUSDT"
        assert body["condition"] == "ABOVE"
        assert body["threshold"] == 80000
        assert body["triggered"] is False

        listed = client.get("/api/alerts").json()["alerts"]
        assert len(listed) == 1


def test_delete_alert() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/alerts",
            json={"symbol": "CRYPTO:BTCUSDT", "condition": "BELOW", "threshold": 100},
        ).json()

        response = client.delete(f"/api/alerts/{created['id']}")

        assert response.status_code == 200
        assert client.get("/api/alerts").json()["alerts"] == []


def test_delete_unknown_alert_returns_404() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/alerts/999999")

    assert response.status_code == 404


def test_post_alert_rejects_unknown_condition() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/alerts",
            json={"symbol": "CRYPTO:BTCUSDT", "condition": "SIDEWAYS", "threshold": 1},
        )

    assert response.status_code == 422


async def test_stream_alerts_wires_engine_into_sse_generator() -> None:
    # Same reasoning as tests/api/test_market.py: the SSE stream never
    # terminates, so drive the route function directly rather than through a
    # real HTTP round trip via TestClient/httpx.ASGITransport, which hangs on it.
    from datetime import UTC, datetime
    from typing import cast

    from fastapi import Request

    from app.alerts.engine import AlertEngine
    from app.db import Database
    from app.market.cache import PriceCache

    db = Database(":memory:")
    db.init_schema([])
    cache = PriceCache()
    engine = AlertEngine(db, cache)
    await engine.create("CRYPTO:BTCUSDT", "ABOVE", 100.0)
    await engine.start()

    class _FakeState:
        def __init__(self) -> None:
            self.alert_engine = engine

    class _FakeApp:
        def __init__(self) -> None:
            self.state = _FakeState()

    class _FakeRequest:
        def __init__(self) -> None:
            self.app = _FakeApp()

    response = await stream_alerts(cast(Request, _FakeRequest()))
    body_iterator = response.body_iterator

    cache.write("CRYPTO:BTCUSDT", 150.0, datetime.now(UTC))
    first_chunk = await anext(body_iterator)  # type: ignore[arg-type]

    assert isinstance(first_chunk, str)
    assert first_chunk.startswith("data: ")
    assert "CRYPTO:BTCUSDT" in first_chunk
    assert '"triggered": true' in first_chunk

    await engine.stop()
