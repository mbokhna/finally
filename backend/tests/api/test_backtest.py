from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_backtest_runs_against_simulator_candles() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/backtest",
            json={
                "symbol": "CRYPTO:BTCUSDT",
                "interval": "1h",
                "limit": 200,
                "strategy": "ma_crossover",
                "params": {"fast": 10, "slow": 30},
                "initial_cash": 10000,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["equity_curve"]) == 200
    assert body["equity_curve"][0]["value"] == 10000.0
    assert "total_return_pct" in body["metrics"]
    assert body["metrics"]["trade_count"] == len(body["trades"])
    for trade in body["trades"]:
        assert trade["side"] in ("BUY", "SELL")
        assert trade["price"] > 0


def test_backtest_rejects_unknown_strategy() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/backtest",
            json={
                "symbol": "CRYPTO:BTCUSDT",
                "params": {"fast": 10, "slow": 30},
                "strategy": "rsi",
            },
        )

    assert response.status_code == 400


def test_backtest_rejects_fast_not_smaller_than_slow() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/backtest",
            json={"symbol": "CRYPTO:BTCUSDT", "params": {"fast": 30, "slow": 10}},
        )

    assert response.status_code == 400


def test_backtest_defaults_apply_when_omitted() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/backtest",
            json={"symbol": "CRYPTO:BTCUSDT", "params": {"fast": 5, "slow": 20}},
        )

    assert response.status_code == 200
    assert len(response.json()["equity_curve"]) == 500  # default limit
