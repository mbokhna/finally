from __future__ import annotations

import asyncio
import contextlib
import hashlib
import math
import random
from datetime import UTC, datetime, timedelta

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.models import Candle
from app.market.seed_prices import (
    GROUP_CORRELATION,
    SEED_BY_SYMBOL,
    SHOCK_MAX_MAGNITUDE,
    SHOCK_MIN_MAGNITUDE,
    SHOCK_PROBABILITY,
    InstrumentSeed,
    default_seed,
)

TICK_SECONDS = 0.5
MIN_PRICE = 0.0001


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            total = sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                lower[i][j] = math.sqrt(matrix[i][i] - total)
            else:
                lower[i][j] = (matrix[i][j] - total) / lower[j][j]
    return lower


def _derive_seed(*parts: str) -> int:
    """Deterministic seed from strings — Python's hash() is randomised per process."""
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:16], 16)


def _gbm_step(price: float, seed: InstrumentSeed, z: float) -> float:
    new_price = price * math.exp((seed.drift - 0.5 * seed.volatility**2) + seed.volatility * z)
    return max(new_price, MIN_PRICE)


class SimulatorDataSource(MarketDataSource):
    """Offline GBM simulator with correlated draws. Seeded RNG => reproducible sequences."""

    def __init__(self, cache: PriceCache, seed: int) -> None:
        self._cache = cache
        self._seed_value = seed
        self._rng = random.Random(seed)
        self._symbols: list[str] = []
        self._prices: dict[str, float] = {}
        self._seeds: dict[str, InstrumentSeed] = {}
        self._task: asyncio.Task[None] | None = None

    async def start(self, symbols: list[str]) -> None:
        for symbol in symbols:
            self._add_symbol_state(symbol)
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def add_symbol(self, symbol: str) -> None:
        if symbol not in self._symbols:
            self._add_symbol_state(symbol)

    async def remove_symbol(self, symbol: str) -> None:
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            del self._prices[symbol]
            del self._seeds[symbol]
            self._cache.remove(symbol)

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        seed = self._seeds.get(symbol) or SEED_BY_SYMBOL.get(symbol) or default_seed(symbol)
        rng = random.Random(_derive_seed(str(self._seed_value), symbol, interval))
        price = seed.start_price
        now = datetime.now(UTC)
        candles: list[Candle] = []
        # Interval-agnostic spacing: synthetic history, not a real interval-aware feed.
        for i in range(limit):
            open_price = price
            close_price = _gbm_step(open_price, seed, rng.gauss(0.0, 1.0))
            high = max(open_price, close_price) * (1 + abs(rng.gauss(0.0, 0.001)))
            low = min(open_price, close_price) * (1 - abs(rng.gauss(0.0, 0.001)))
            volume = abs(rng.gauss(1000.0, 200.0))
            timestamp = now - timedelta(hours=(limit - i))
            candles.append(
                Candle(t=timestamp, o=open_price, h=high, l=low, c=close_price, v=volume)
            )
            price = close_price
        return candles

    def _add_symbol_state(self, symbol: str) -> None:
        seed = SEED_BY_SYMBOL.get(symbol)
        if seed is None:
            seed = default_seed(symbol)
        self._symbols.append(symbol)
        self._seeds[symbol] = seed
        self._prices[symbol] = seed.start_price
        self._cache.write(symbol, seed.start_price, datetime.now(UTC))

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            self._tick()

    def _tick(self) -> None:
        symbols = self._symbols
        n = len(symbols)
        if n == 0:
            return

        z = [self._rng.gauss(0.0, 1.0) for _ in range(n)]
        correlated = self._correlated_draws(symbols, z)
        now = datetime.now(UTC)

        for symbol, zi in zip(symbols, correlated, strict=True):
            seed = self._seeds[symbol]
            new_price = _gbm_step(self._prices[symbol], seed, zi)

            if self._rng.random() < SHOCK_PROBABILITY:
                magnitude = self._rng.uniform(SHOCK_MIN_MAGNITUDE, SHOCK_MAX_MAGNITUDE)
                sign = 1.0 if self._rng.random() < 0.5 else -1.0
                new_price = max(new_price * (1 + sign * magnitude), MIN_PRICE)

            self._prices[symbol] = new_price
            self._cache.write(symbol, new_price, now)

    def _correlated_draws(self, symbols: list[str], z: list[float]) -> list[float]:
        n = len(symbols)
        groups = [self._seeds[s].group for s in symbols]
        corr = [
            [1.0 if i == j else GROUP_CORRELATION[(groups[i], groups[j])] for j in range(n)]
            for i in range(n)
        ]
        lower = _cholesky(corr)
        return [sum(lower[i][k] * z[k] for k in range(i + 1)) for i in range(n)]
