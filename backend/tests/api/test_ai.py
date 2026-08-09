from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


def _sse_chunk(content: str) -> str:
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload)}\n\n"


def test_ai_status_unconfigured_by_default() -> None:
    with TestClient(app) as client:
        response = client.get("/api/ai/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_ai_chat_returns_503_when_unconfigured() -> None:
    with TestClient(app) as client:
        response = client.post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 503


def test_health_reports_ai_unconfigured_by_default() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ai"] == "unconfigured"


def test_every_other_endpoint_still_works_with_no_key_set() -> None:
    # The core "AI is optional" guarantee (PLAN.md §11): nothing else breaks.
    with TestClient(app) as client:
        assert client.get("/api/prices").status_code == 200
        assert client.get("/api/portfolio").status_code == 200
        assert client.get("/api/watchlist").status_code == 200
        assert client.get("/api/alerts").status_code == 200
        assert client.get("/api/trades").status_code == 200


def test_ai_status_configured_when_key_and_free_model_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/some-model:free")

    with TestClient(app) as client:
        response = client.get("/api/ai/status")

    assert response.json() == {"configured": True, "model": "some-provider/some-model:free"}


def test_ai_status_unconfigured_when_model_is_not_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/paid-model")

    with TestClient(app) as client:
        response = client.get("/api/ai/status")

    assert response.json()["configured"] is False


def test_ai_chat_streams_reply_and_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/some-model:free")

    proposal_json = (
        '{"action": "SELL", "symbol": "CRYPTO:BTCUSDT", "quantity": 0.01, '
        '"reason": "take profit"}'
    )
    sse_body = (
        _sse_chunk("Your BTC position is up. ")
        + _sse_chunk(f"```proposal\n{proposal_json}\n```")
        + "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body)

    with TestClient(app) as client:
        app.state.ai_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post("/api/ai/chat", json={"message": "How's my BTC doing?"})

    assert response.status_code == 200
    body = response.text
    assert "event: token" in body
    assert "Your BTC position is up." in body
    assert "```" not in body
    assert "event: proposal" in body
    assert '"action": "SELL"' in body
    assert '"symbol": "CRYPTO:BTCUSDT"' in body


def test_ai_chat_passes_through_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/some-model:free")

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content="data: [DONE]\n\n")

    with TestClient(app) as client:
        app.state.ai_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post(
            "/api/ai/chat",
            json={
                "message": "and now?",
                "history": [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                ],
            },
        )

    assert response.status_code == 200
    body = captured["body"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert messages[1] == {"role": "user", "content": "first question"}
    assert messages[2] == {"role": "assistant", "content": "first answer"}
    assert messages[3] == {"role": "user", "content": "and now?"}


def test_ai_chat_returns_429_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/some-model:free")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    with TestClient(app) as client:
        app.state.ai_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 429


def test_ai_chat_returns_503_on_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("PULSEDESK_AI_MODEL", "some-provider/some-model:free")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    with TestClient(app) as client:
        app.state.ai_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 503
