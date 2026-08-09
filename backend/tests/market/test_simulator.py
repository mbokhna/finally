from __future__ import annotations

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource

SYMBOLS = ["CRYPTO:BTCUSDT", "CRYPTO:ETHUSDT", "GPW:PKN", "GPW:PKO"]


def _primed(seed: int) -> SimulatorDataSource:
    sim = SimulatorDataSource(PriceCache(), seed=seed)
    for symbol in SYMBOLS:
        sim._add_symbol_state(symbol)
    return sim


def test_same_seed_produces_identical_price_sequence() -> None:
    sim_a = _primed(42)
    sim_b = _primed(42)

    for _ in range(20):
        sim_a._tick()
        sim_b._tick()

    assert sim_a._prices == sim_b._prices


def test_different_seed_diverges() -> None:
    sim_a = _primed(1)
    sim_b = _primed(2)

    for _ in range(5):
        sim_a._tick()
        sim_b._tick()

    assert sim_a._prices != sim_b._prices


def test_tick_writes_through_to_cache() -> None:
    cache = PriceCache()
    sim = SimulatorDataSource(cache, seed=42)
    for symbol in SYMBOLS:
        sim._add_symbol_state(symbol)
    _, version_before = cache.snapshot()

    sim._tick()

    snapshot, version_after = cache.snapshot()
    assert version_after == version_before + len(SYMBOLS)
    assert {u.symbol for u in snapshot} == set(SYMBOLS)


async def test_start_populates_cache_and_stop_is_idempotent() -> None:
    cache = PriceCache()
    sim = SimulatorDataSource(cache, seed=7)

    await sim.start(SYMBOLS)
    snapshot, _ = cache.snapshot()
    assert {u.symbol for u in snapshot} == set(SYMBOLS)
    assert sim.get_symbols() == SYMBOLS

    await sim.stop()
    await sim.stop()


async def test_add_and_remove_symbol() -> None:
    cache = PriceCache()
    sim = SimulatorDataSource(cache, seed=7)
    await sim.start([])

    await sim.add_symbol("CRYPTO:SOLUSDT")
    assert "CRYPTO:SOLUSDT" in sim.get_symbols()
    assert cache.get("CRYPTO:SOLUSDT") is not None

    await sim.add_symbol("CRYPTO:SOLUSDT")
    assert sim.get_symbols().count("CRYPTO:SOLUSDT") == 1

    await sim.remove_symbol("CRYPTO:SOLUSDT")
    assert "CRYPTO:SOLUSDT" not in sim.get_symbols()
    assert cache.get("CRYPTO:SOLUSDT") is None

    await sim.remove_symbol("CRYPTO:SOLUSDT")

    await sim.stop()


async def test_add_symbol_without_preset_seed_does_not_crash() -> None:
    cache = PriceCache()
    sim = SimulatorDataSource(cache, seed=7)
    await sim.start([])

    await sim.add_symbol("CRYPTO:DOGEUSDT")

    assert cache.get("CRYPTO:DOGEUSDT") is not None
    await sim.stop()


async def test_get_candles_is_deterministic_and_newest_last() -> None:
    sim_a = SimulatorDataSource(PriceCache(), seed=99)
    sim_b = SimulatorDataSource(PriceCache(), seed=99)

    candles_a = await sim_a.get_candles("CRYPTO:BTCUSDT", "1h", 30)
    candles_b = await sim_b.get_candles("CRYPTO:BTCUSDT", "1h", 30)

    assert len(candles_a) == 30
    ohlcv_a = [(c.o, c.h, c.l, c.c, c.v) for c in candles_a]
    ohlcv_b = [(c.o, c.h, c.l, c.c, c.v) for c in candles_b]
    assert ohlcv_a == ohlcv_b
    assert candles_a[0].t < candles_a[-1].t
