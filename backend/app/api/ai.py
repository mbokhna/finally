from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal, cast

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.ai.client import iter_tokens, open_chat_stream
from app.ai.context import build_context
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.proposals import Proposal, extract_proposal
from app.alerts.engine import AlertEngine
from app.config import Settings
from app.errors import RateLimitedError, UpstreamUnavailableError
from app.market.cache import PriceCache
from app.portfolio.service import PortfolioService

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


def _get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.ai_http_client)


async def _gather_context(request: Request) -> str:
    portfolio_service = cast(PortfolioService, request.app.state.portfolio_service)
    cache = cast(PriceCache, request.app.state.price_cache)
    alert_engine = cast(AlertEngine, request.app.state.alert_engine)

    valuation = await portfolio_service.get_valuation()
    trades = await portfolio_service.get_trades(10)
    alerts = await alert_engine.list_all()
    prices, _version = cache.snapshot()

    return build_context(valuation, prices, trades, alerts)


def _serialize_proposal(proposal: Proposal) -> dict[str, object]:
    return {
        "action": proposal.action,
        "symbol": proposal.symbol,
        "quantity": proposal.quantity,
        "reason": proposal.reason,
    }


@router.get("/api/ai/status")
async def get_ai_status(request: Request) -> dict[str, object]:
    settings = _get_settings(request)
    return {"configured": settings.ai_configured, "model": settings.ai_model}


@router.post("/api/ai/chat")
async def post_ai_chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    settings = _get_settings(request)
    if not settings.ai_configured or settings.openrouter_api_key is None:
        raise UpstreamUnavailableError("AI assistant not configured")

    context = await _gather_context(request)
    history = [{"role": m.role, "content": m.content} for m in payload.history]

    response = await open_chat_stream(
        _get_http_client(request),
        settings.openrouter_api_key,
        settings.ai_model,
        settings.ai_max_tokens,
        SYSTEM_PROMPT,
        context,
        history,
        payload.message,
    )

    if response.status_code == 429:
        await response.aclose()
        raise RateLimitedError("OpenRouter rate limited — try again shortly")
    if response.status_code >= 400:
        await response.aclose()
        raise UpstreamUnavailableError(f"OpenRouter error {response.status_code}")

    return StreamingResponse(_sse_chat_events(response), media_type="text/event-stream")


async def _sse_chat_events(response: httpx.Response) -> AsyncIterator[str]:
    full_text = ""
    async for token in iter_tokens(response):
        full_text += token

    extracted = extract_proposal(full_text)
    if extracted.prose:
        yield f"event: token\ndata: {json.dumps({'text': extracted.prose})}\n\n"
    if extracted.proposal is not None:
        yield f"event: proposal\ndata: {json.dumps(_serialize_proposal(extracted.proposal))}\n\n"
