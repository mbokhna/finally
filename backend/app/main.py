from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.market import router as market_router
from app.config import get_settings
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.seed_prices import SEEDS

DEFAULT_WATCHLIST = [seed.symbol for seed in SEEDS]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    cache = PriceCache()
    source = create_market_data_source(cache, settings)
    await source.start(DEFAULT_WATCHLIST)

    app.state.price_cache = cache
    app.state.market_data_source = source

    yield

    await source.stop()


app = FastAPI(title="PulseDesk", lifespan=lifespan)
app.include_router(market_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
