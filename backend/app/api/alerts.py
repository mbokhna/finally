from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.alerts.engine import AlertEngine
from app.alerts.models import Alert, Condition
from app.errors import NotFoundError

router = APIRouter()


class AlertRequest(BaseModel):
    symbol: str
    condition: Condition
    threshold: float


def _get_engine(request: Request) -> AlertEngine:
    return cast(AlertEngine, request.app.state.alert_engine)


def _serialize(alert: Alert) -> dict[str, object]:
    return {
        "id": alert.id,
        "symbol": alert.symbol,
        "condition": alert.condition,
        "threshold": alert.threshold,
        "triggered": alert.triggered,
        "created_at": alert.created_at.isoformat(),
    }


@router.get("/api/alerts")
async def get_alerts(request: Request) -> dict[str, object]:
    alerts = await _get_engine(request).list_all()
    return {"alerts": [_serialize(alert) for alert in alerts]}


@router.post("/api/alerts")
async def post_alert(payload: AlertRequest, request: Request) -> dict[str, object]:
    alert = await _get_engine(request).create(payload.symbol, payload.condition, payload.threshold)
    return _serialize(alert)


@router.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, request: Request) -> dict[str, object]:
    removed = await _get_engine(request).delete(alert_id)
    if not removed:
        raise NotFoundError(f"Alert {alert_id} not found")
    return {"status": "deleted"}


@router.get("/api/stream/alerts")
async def stream_alerts(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _sse_alert_events(_get_engine(request)), media_type="text/event-stream"
    )


async def _sse_alert_events(engine: AlertEngine) -> AsyncIterator[str]:
    async for alert in engine.events():
        yield f"data: {json.dumps(_serialize(alert))}\n\n"
