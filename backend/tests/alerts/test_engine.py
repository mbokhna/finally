from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.alerts.engine import AlertEngine
from app.db import Database
from app.market.cache import PriceCache

SYMBOL = "CRYPTO:BTCUSDT"


def _engine() -> tuple[AlertEngine, Database, PriceCache]:
    db = Database(":memory:")
    db.init_schema([])
    cache = PriceCache()
    return AlertEngine(db, cache), db, cache


async def test_create_and_list() -> None:
    engine, _db, _cache = _engine()

    created = await engine.create(SYMBOL, "ABOVE", 80000.0)

    assert created.triggered is False
    listed = await engine.list_all()
    assert listed == [created]


async def test_delete_returns_false_for_unknown_id() -> None:
    engine, _db, _cache = _engine()

    assert await engine.delete(999) is False


async def test_alert_fires_above_and_only_once() -> None:
    engine, _db, cache = _engine()
    await engine.create(SYMBOL, "ABOVE", 100.0)
    await engine.start()

    subscriber = engine.events()
    fire_task = asyncio.ensure_future(anext(subscriber))

    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    fired = await asyncio.wait_for(fire_task, timeout=2.0)

    assert fired.symbol == SYMBOL
    assert fired.triggered is True

    alerts = await engine.list_all()
    assert alerts[0].triggered is True

    # Further price movement above the threshold must not fire again.
    second_task = asyncio.ensure_future(anext(subscriber))
    cache.write(SYMBOL, 200.0, datetime.now(UTC))
    done, _pending = await asyncio.wait({second_task}, timeout=0.3)
    assert not done
    second_task.cancel()

    await engine.stop()


async def test_alert_fires_below() -> None:
    engine, _db, cache = _engine()
    await engine.create(SYMBOL, "BELOW", 50.0)
    await engine.start()

    subscriber = engine.events()
    fire_task = asyncio.ensure_future(anext(subscriber))

    cache.write(SYMBOL, 40.0, datetime.now(UTC))
    fired = await asyncio.wait_for(fire_task, timeout=2.0)

    assert fired.condition == "BELOW"
    assert fired.triggered is True

    await engine.stop()


async def test_alert_does_not_fire_before_threshold_is_crossed() -> None:
    engine, _db, cache = _engine()
    await engine.create(SYMBOL, "ABOVE", 100.0)
    await engine.start()

    cache.write(SYMBOL, 50.0, datetime.now(UTC))
    await asyncio.sleep(0.3)

    alerts = await engine.list_all()
    assert alerts[0].triggered is False

    await engine.stop()


async def test_deleted_alert_never_fires() -> None:
    engine, _db, cache = _engine()
    created = await engine.create(SYMBOL, "ABOVE", 100.0)
    await engine.start()

    await engine.delete(created.id)
    cache.write(SYMBOL, 999.0, datetime.now(UTC))
    await asyncio.sleep(0.3)

    assert await engine.list_all() == []

    await engine.stop()


async def test_two_subscribers_both_receive_the_fire() -> None:
    engine, _db, cache = _engine()
    await engine.create(SYMBOL, "ABOVE", 100.0)
    await engine.start()

    sub_a = engine.events()
    sub_b = engine.events()
    task_a = asyncio.ensure_future(anext(sub_a))
    task_b = asyncio.ensure_future(anext(sub_b))
    await asyncio.sleep(0.01)  # let both subscriber queues register

    cache.write(SYMBOL, 150.0, datetime.now(UTC))

    fired_a = await asyncio.wait_for(task_a, timeout=2.0)
    fired_b = await asyncio.wait_for(task_b, timeout=2.0)
    assert fired_a.id == fired_b.id

    await engine.stop()


async def test_stop_is_idempotent() -> None:
    engine, _db, _cache = _engine()
    await engine.start()

    await engine.stop()
    await engine.stop()


async def test_alert_with_no_price_never_fires() -> None:
    engine, _db, _cache = _engine()
    await engine.create("GPW:UNPRICED", "ABOVE", 1.0)
    await engine.start()

    await asyncio.sleep(0.3)

    alerts = await engine.list_all()
    assert alerts[0].triggered is False

    await engine.stop()
