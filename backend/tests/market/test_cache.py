from __future__ import annotations

from datetime import UTC, datetime

from app.market.cache import PriceCache


def test_write_increments_version_and_stores_update() -> None:
    cache = PriceCache()
    _, version_before = cache.snapshot()

    update = cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))

    snapshot, version_after = cache.snapshot()
    assert version_after == version_before + 1
    assert snapshot == [update]
    assert update.previous_price is None


def test_second_write_carries_previous_price() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))

    update = cache.write("CRYPTO:BTCUSDT", 105.0, datetime.now(UTC))

    assert update.previous_price == 100.0
    assert update.price == 105.0


def test_remove_clears_entry_and_bumps_version() -> None:
    cache = PriceCache()
    cache.write("CRYPTO:BTCUSDT", 100.0, datetime.now(UTC))
    _, version_before = cache.snapshot()

    cache.remove("CRYPTO:BTCUSDT")

    snapshot, version_after = cache.snapshot()
    assert snapshot == []
    assert version_after == version_before + 1
    assert cache.get("CRYPTO:BTCUSDT") is None


def test_remove_unknown_symbol_is_noop() -> None:
    cache = PriceCache()
    _, version_before = cache.snapshot()

    cache.remove("CRYPTO:UNKNOWN")

    _, version_after = cache.snapshot()
    assert version_after == version_before
