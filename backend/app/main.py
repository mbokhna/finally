from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.market import router as market_router
from app.api.portfolio import router as portfolio_router
from app.api.watchlist import router as watchlist_router
from app.config import get_settings
from app.db import Database
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.seed_prices import SEEDS
from app.portfolio.service import PortfolioService

DEFAULT_WATCHLIST = [seed.symbol for seed in SEEDS]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    db = Database(settings.db_path)
    db.init_schema(DEFAULT_WATCHLIST)
    watchlist = db.get_watchlist()

    cache = PriceCache()
    source = create_market_data_source(cache, settings)
    await source.start(watchlist)

    app.state.db = db
    app.state.price_cache = cache
    app.state.market_data_source = source
    app.state.portfolio_service = PortfolioService(db, cache, settings.currency)

    yield

    await source.stop()
    db.close()


app = FastAPI(title="PulseDesk", lifespan=lifespan)
register_error_handlers(app)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
