from __future__ import annotations

from datetime import UTC, datetime

from app.market.models import PriceUpdate


def test_change_and_direction_up() -> None:
    update = PriceUpdate(
        symbol="CRYPTO:BTCUSDT", price=105.0, previous_price=100.0, timestamp=datetime.now(UTC)
    )
    assert update.change == 5.0
    assert update.direction == "up"


def test_change_and_direction_down() -> None:
    update = PriceUpdate(
        symbol="CRYPTO:BTCUSDT", price=95.0, previous_price=100.0, timestamp=datetime.now(UTC)
    )
    assert update.change == -5.0
    assert update.direction == "down"


def test_change_and_direction_flat_on_equal_price() -> None:
    update = PriceUpdate(
        symbol="CRYPTO:BTCUSDT", price=100.0, previous_price=100.0, timestamp=datetime.now(UTC)
    )
    assert update.change == 0.0
    assert update.direction == "flat"


def test_no_previous_price_is_flat_with_no_change() -> None:
    update = PriceUpdate(
        symbol="CRYPTO:BTCUSDT", price=100.0, previous_price=None, timestamp=datetime.now(UTC)
    )
    assert update.change is None
    assert update.direction == "flat"
