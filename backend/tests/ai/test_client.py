from __future__ import annotations

import json

import httpx
import pytest

from app.ai.client import iter_tokens, open_chat_stream
from app.errors import UpstreamUnavailableError


def _sse_chunk(content: str) -> str:
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload)}\n\n"


async def test_iter_tokens_yields_content_deltas_in_order() -> None:
    body = _sse_chunk("Hello") + _sse_chunk(", world") + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await open_chat_stream(
        http_client, "sk-test", "some/model:free", 100, "system", "context", [], "hi"
    )

    tokens = [token async for token in iter_tokens(response)]

    assert tokens == ["Hello", ", world"]
    await http_client.aclose()


async def test_iter_tokens_skips_non_data_lines_and_malformed_json() -> None:
    body = ": heartbeat\n\n" + "data: not-json\n\n" + _sse_chunk("ok") + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await open_chat_stream(
        http_client, "sk-test", "some/model:free", 100, "system", "context", [], "hi"
    )

    tokens = [token async for token in iter_tokens(response)]

    assert tokens == ["ok"]
    await http_client.aclose()


async def test_open_chat_stream_sends_auth_header_and_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content="data: [DONE]\n\n")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await open_chat_stream(
        http_client,
        "sk-test-key",
        "some/model:free",
        123,
        "SYSTEM PROMPT",
        "CONTEXT HERE",
        [{"role": "user", "content": "earlier"}],
        "current message",
    )
    await response.aclose()

    assert captured["auth"] == "Bearer sk-test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "some/model:free"
    assert body["max_tokens"] == 123
    assert body["stream"] is True
    messages = body["messages"]
    assert messages[0] == {"role": "system", "content": "SYSTEM PROMPT\n\nCONTEXT HERE"}
    assert messages[1] == {"role": "user", "content": "earlier"}
    assert messages[2] == {"role": "user", "content": "current message"}

    await http_client.aclose()


async def test_open_chat_stream_surfaces_status_code_without_raising() -> None:
    # 429/5xx handling is the caller's job (it needs to decide the outer HTTP
    # response before any body is read) — the client just hands back the response.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await open_chat_stream(
        http_client, "sk-test", "some/model:free", 100, "system", "context", [], "hi"
    )

    assert response.status_code == 429
    await response.aclose()
    await http_client.aclose()


async def test_open_chat_stream_wraps_connection_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(UpstreamUnavailableError):
        await open_chat_stream(
            http_client, "sk-test", "some/model:free", 100, "system", "context", [], "hi"
        )

    await http_client.aclose()
