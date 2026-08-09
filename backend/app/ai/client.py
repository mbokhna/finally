from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.errors import UpstreamUnavailableError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def open_chat_stream(
    http_client: httpx.AsyncClient,
    api_key: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    context: str,
    history: list[dict[str, str]],
    message: str,
) -> httpx.Response:
    """Opens the OpenRouter stream and returns once headers arrive.

    Returning before reading the body lets the caller inspect `status_code`
    (429, 5xx) and raise a normal HTTP error instead of committing to a 200 SSE
    response first — once that starts, the status code can no longer change.
    The caller must eventually call `await response.aclose()`.
    """
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n{context}"},
        *history,
        {"role": "user", "content": message},
    ]
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    request = http_client.build_request("POST", OPENROUTER_URL, headers=headers, json=payload)
    try:
        return await http_client.send(request, stream=True)
    except httpx.HTTPError as exc:
        raise UpstreamUnavailableError(f"OpenRouter request failed: {exc}") from exc


async def iter_tokens(response: httpx.Response) -> AsyncIterator[str]:
    """Yields text deltas from an already-open OpenRouter SSE response.

    Closes the response when the stream ends, errors, or the caller stops
    iterating early (e.g. the browser disconnects).
    """
    try:
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[len("data: ") :].strip()
            if data == "[DONE]":
                break
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = parsed.get("choices") if isinstance(parsed, dict) else None
            if not choices:
                continue
            token = choices[0].get("delta", {}).get("content")
            if isinstance(token, str) and token:
                yield token
    finally:
        await response.aclose()
