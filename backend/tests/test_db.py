from __future__ import annotations

import pytest

from app.db import Database


def test_init_schema_seeds_default_cash_and_watchlist() -> None:
    db = Database(":memory:")

    db.init_schema(["CRYPTO:BTCUSDT", "GPW:PKN"])

    assert db.get_cash() == 100_000.0
    assert db.get_watchlist() == ["CRYPTO:BTCUSDT", "GPW:PKN"]


def test_init_schema_does_not_reseed_on_second_call() -> None:
    db = Database(":memory:")
    db.init_schema(["CRYPTO:BTCUSDT"])
    db.set_cash(500.0)

    db.init_schema(["CRYPTO:BTCUSDT", "GPW:PKN"])  # simulates a restart

    assert db.get_cash() == 500.0
    assert db.get_watchlist() == ["CRYPTO:BTCUSDT"]


def test_position_upsert_get_and_delete() -> None:
    db = Database(":memory:")
    db.init_schema([])

    assert db.get_position("CRYPTO:BTCUSDT") is None

    db.upsert_position("CRYPTO:BTCUSDT", 1.5, 100.0)
    assert db.get_position("CRYPTO:BTCUSDT") == (1.5, 100.0)

    db.upsert_position("CRYPTO:BTCUSDT", 2.0, 120.0)
    assert db.get_position("CRYPTO:BTCUSDT") == (2.0, 120.0)

    db.delete_position("CRYPTO:BTCUSDT")
    assert db.get_position("CRYPTO:BTCUSDT") is None


def test_insert_trade_and_get_trades_newest_first() -> None:
    db = Database(":memory:")
    db.init_schema([])

    db.insert_trade("CRYPTO:BTCUSDT", "BUY", 1.0, 100.0)
    db.insert_trade("CRYPTO:BTCUSDT", "SELL", 0.5, 110.0)

    trades = db.get_trades(10)
    assert [trade[2] for trade in trades] == ["SELL", "BUY"]


def test_watchlist_add_ignores_duplicate_and_remove_reports_existence() -> None:
    db = Database(":memory:")
    db.init_schema([])

    db.add_watchlist_symbol("CRYPTO:SOLUSDT")
    db.add_watchlist_symbol("CRYPTO:SOLUSDT")
    assert db.get_watchlist() == ["CRYPTO:SOLUSDT"]

    assert db.remove_watchlist_symbol("CRYPTO:SOLUSDT") is True
    assert db.remove_watchlist_symbol("CRYPTO:SOLUSDT") is False
    assert db.get_watchlist() == []


async def test_run_offloads_to_a_thread_and_commits() -> None:
    db = Database(":memory:")
    db.init_schema([])

    def _op() -> float:
        db.set_cash(42.0)
        return db.get_cash()

    result = await db.run(_op)

    assert result == 42.0
    assert db.get_cash() == 42.0


async def test_run_rolls_back_on_exception() -> None:
    db = Database(":memory:")
    db.init_schema([])

    def _op() -> None:
        db.set_cash(1.0)
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await db.run(_op)

    assert db.get_cash() == 100_000.0
