from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.portfolio.models import PortfolioValuation, Trade
from app.portfolio.service import PortfolioService

router = APIRouter()


class TradeRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float


def _get_service(request: Request) -> PortfolioService:
    return cast(PortfolioService, request.app.state.portfolio_service)


def _serialize_trade(trade: Trade) -> dict[str, object]:
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "executed_at": trade.executed_at.isoformat(),
    }


def _serialize_valuation(valuation: PortfolioValuation) -> dict[str, object]:
    return {
        "cash": valuation.cash,
        "positions": [
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "avg_cost": position.avg_cost,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "unrealised_pnl": position.unrealised_pnl,
                "unrealised_pnl_pct": position.unrealised_pnl_pct,
            }
            for position in valuation.positions
        ],
        "total_value": valuation.total_value,
        "currency": valuation.currency,
    }


@router.get("/api/portfolio")
async def get_portfolio(request: Request) -> dict[str, object]:
    valuation = await _get_service(request).get_valuation()
    return _serialize_valuation(valuation)


@router.post("/api/trade")
async def post_trade(payload: TradeRequest, request: Request) -> dict[str, object]:
    service = _get_service(request)
    if payload.side == "BUY":
        trade, cash = await service.buy(payload.symbol, payload.quantity)
    else:
        trade, cash = await service.sell(payload.symbol, payload.quantity)
    return {"trade": _serialize_trade(trade), "cash": cash}


@router.get("/api/trades")
async def get_trades(request: Request, limit: int = 50) -> dict[str, object]:
    trades = await _get_service(request).get_trades(limit)
    return {"trades": [_serialize_trade(trade) for trade in trades]}
