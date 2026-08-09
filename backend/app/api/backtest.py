from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.backtest.runner import BacktestResult, run_ma_crossover
from app.backtest.strategies import MACrossoverParams
from app.errors import ValidationError
from app.market.interface import MarketDataSource

router = APIRouter()


class MACrossoverRequestParams(BaseModel):
    fast: int
    slow: int


class BacktestRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    limit: int = 500
    strategy: str = "ma_crossover"
    params: MACrossoverRequestParams
    initial_cash: float = 10000.0


def _get_source(request: Request) -> MarketDataSource:
    return cast(MarketDataSource, request.app.state.market_data_source)


def _serialize(result: BacktestResult) -> dict[str, object]:
    return {
        "trades": [
            {
                "t": trade.t.isoformat(),
                "side": trade.side,
                "price": trade.price,
                "quantity": trade.quantity,
            }
            for trade in result.trades
        ],
        "equity_curve": [
            {"t": point.t.isoformat(), "value": point.value} for point in result.equity_curve
        ],
        "metrics": {
            "total_return_pct": result.metrics.total_return_pct,
            "max_drawdown_pct": result.metrics.max_drawdown_pct,
            "trade_count": result.metrics.trade_count,
        },
    }


@router.post("/api/backtest")
async def post_backtest(payload: BacktestRequest, request: Request) -> dict[str, object]:
    if payload.strategy != "ma_crossover":
        raise ValidationError(f"Unknown strategy: {payload.strategy!r}")
    if payload.params.fast <= 0 or payload.params.slow <= 0:
        raise ValidationError("fast and slow windows must be positive")
    if payload.params.fast >= payload.params.slow:
        raise ValidationError("fast window must be smaller than slow window")
    if payload.initial_cash <= 0:
        raise ValidationError("initial_cash must be positive")

    source = _get_source(request)
    candles = await source.get_candles(payload.symbol, payload.interval, payload.limit)
    result = run_ma_crossover(
        candles,
        MACrossoverParams(fast=payload.params.fast, slow=payload.params.slow),
        payload.initial_cash,
    )
    return _serialize(result)
