from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok_and_ai_unconfigured_by_default() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["market_mode"] == "simulator"
    assert body["ai"] == "unconfigured"
