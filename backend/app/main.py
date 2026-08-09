from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.alerts.engine import AlertEngine
from app.api.alerts import router as alerts_router
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
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    db = Database(settings.db_path)
    db.init_schema(DEFAULT_WATCHLIST)
    watchlist = db.get_watchlist()

    cache = PriceCache()
    source = create_market_data_source(cache, settings)
    await source.start(watchlist)

    alert_engine = AlertEngine(db, cache)
    await alert_engine.start()

    app.state.db = db
    app.state.price_cache = cache
    app.state.market_data_source = source
    app.state.portfolio_service = PortfolioService(db, cache, settings.currency)
    app.state.alert_engine = alert_engine

    yield

    await alert_engine.stop()
    await source.stop()
    db.close()


app = FastAPI(title="PulseDesk", lifespan=lifespan)
register_error_handlers(app)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(alerts_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted last and only if present: /api/* above always wins, and a backend-only
# checkout (frontend not built yet) still starts fine without it.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
