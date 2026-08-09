from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import Database
from app.errors import NotFoundError, ValidationError
from app.market.interface import MarketDataSource

router = APIRouter()

KNOWN_PREFIXES = {"CRYPTO", "GPW"}


class WatchlistRequest(BaseModel):
    symbol: str


def _get_db(request: Request) -> Database:
    return cast(Database, request.app.state.db)


def _get_source(request: Request) -> MarketDataSource:
    return cast(MarketDataSource, request.app.state.market_data_source)


def _validate_symbol(symbol: str) -> None:
    prefix = symbol.split(":", 1)[0]
    if prefix not in KNOWN_PREFIXES:
        raise ValidationError(f"Unknown market prefix: {prefix!r}")


@router.get("/api/watchlist")
async def get_watchlist(request: Request) -> dict[str, object]:
    db = _get_db(request)
    symbols = await db.run(db.get_watchlist)
    return {"symbols": symbols}


@router.post("/api/watchlist")
async def post_watchlist(payload: WatchlistRequest, request: Request) -> dict[str, object]:
    _validate_symbol(payload.symbol)
    db = _get_db(request)

    def _op() -> list[str]:
        db.add_watchlist_symbol(payload.symbol)
        return db.get_watchlist()

    symbols = await db.run(_op)
    await _get_source(request).add_symbol(payload.symbol)
    return {"symbols": symbols}


@router.delete("/api/watchlist/{symbol}")
async def delete_watchlist_symbol(symbol: str, request: Request) -> dict[str, object]:
    db = _get_db(request)

    def _op() -> tuple[bool, list[str]]:
        removed = db.remove_watchlist_symbol(symbol)
        return removed, db.get_watchlist()

    removed, symbols = await db.run(_op)
    if not removed:
        raise NotFoundError(f"{symbol} is not on the watchlist")
    return {"symbols": symbols}
