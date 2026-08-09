from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_get_portfolio_returns_seed_state() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash"] == 100_000.0
    assert body["positions"] == []
    assert body["currency"] == "PLN"


def test_buy_then_sell_round_trip() -> None:
    with TestClient(app) as client:
        buy_response = client.post(
            "/api/trade", json={"symbol": "CRYPTO:BTCUSDT", "side": "BUY", "quantity": 0.01}
        )
        assert buy_response.status_code == 200
        assert buy_response.json()["cash"] < 100_000.0

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["positions"][0]["symbol"] == "CRYPTO:BTCUSDT"

        sell_response = client.post(
            "/api/trade", json={"symbol": "CRYPTO:BTCUSDT", "side": "SELL", "quantity": 0.01}
        )
        assert sell_response.status_code == 200

        trades = client.get("/api/trades").json()["trades"]
        assert [trade["side"] for trade in trades] == ["SELL", "BUY"]


def test_buy_insufficient_cash_returns_409() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/trade",
            json={"symbol": "CRYPTO:BTCUSDT", "side": "BUY", "quantity": 1_000_000},
        )

    assert response.status_code == 409
    assert "Insufficient cash" in response.json()["detail"]


def test_sell_insufficient_shares_returns_409() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/trade", json={"symbol": "CRYPTO:BTCUSDT", "side": "SELL", "quantity": 1}
        )

    assert response.status_code == 409


def test_trade_unpriced_symbol_returns_503() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/trade", json={"symbol": "CRYPTO:UNKNOWNCOIN", "side": "BUY", "quantity": 1}
        )

    assert response.status_code == 503
