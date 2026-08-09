from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import DEFAULT_WATCHLIST, app


def test_get_watchlist_returns_default_seed() -> None:
    with TestClient(app) as client:
        response = client.get("/api/watchlist")

    assert response.status_code == 200
    assert response.json()["symbols"] == DEFAULT_WATCHLIST


def test_post_watchlist_adds_symbol_and_starts_pricing() -> None:
    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "CRYPTO:DOGEUSDT"})
        assert response.status_code == 200
        assert "CRYPTO:DOGEUSDT" in response.json()["symbols"]

        prices = client.get("/api/prices").json()
        symbols = {p["symbol"] for p in prices["prices"]}
        assert "CRYPTO:DOGEUSDT" in symbols


def test_post_watchlist_unknown_prefix_returns_400() -> None:
    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "NASDAQ:AAPL"})

    assert response.status_code == 400


def test_delete_watchlist_symbol() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/watchlist/CRYPTO:XRPUSDT")

    assert response.status_code == 200
    assert "CRYPTO:XRPUSDT" not in response.json()["symbols"]


def test_delete_unknown_watchlist_symbol_returns_404() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/watchlist/CRYPTO:NOTLISTED")

    assert response.status_code == 404
