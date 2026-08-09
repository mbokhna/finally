from __future__ import annotations

from app.config import Settings
from app.market.cache import PriceCache
from app.market.composite import CompositeDataSource
from app.market.interface import MarketDataSource
from app.market.simulator import SimulatorDataSource


def create_market_data_source(cache: PriceCache, settings: Settings) -> MarketDataSource:
    if settings.market_mode == "simulator":
        return SimulatorDataSource(cache, seed=settings.seed)
    return CompositeDataSource(cache, settings)
