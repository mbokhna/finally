from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db import Database
from app.errors import BusinessRuleError, UpstreamUnavailableError, ValidationError
from app.market.cache import PriceCache
from app.portfolio.service import PortfolioService

SYMBOL = "CRYPTO:BTCUSDT"


def _service() -> tuple[PortfolioService, Database, PriceCache]:
    db = Database(":memory:")
    db.init_schema([])
    cache = PriceCache()
    return PortfolioService(db, cache, "PLN"), db, cache


async def test_buy_then_buy_again_then_partial_sell_is_correct() -> None:
    # The Phase 3 "done when": buy 10, buy 10 more at a different price, sell 5.
    service, _db, cache = _service()

    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    trade1, cash1 = await service.buy(SYMBOL, 10)
    assert trade1.side == "BUY"
    assert cash1 == pytest.approx(99_000.0)

    cache.write(SYMBOL, 200.0, datetime.now(UTC))
    _, cash2 = await service.buy(SYMBOL, 10)
    assert cash2 == pytest.approx(97_000.0)

    positions = await service.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == pytest.approx(20.0)
    assert positions[0].avg_cost == pytest.approx(150.0)

    cache.write(SYMBOL, 180.0, datetime.now(UTC))
    trade3, cash3 = await service.sell(SYMBOL, 5)
    assert trade3.side == "SELL"
    assert cash3 == pytest.approx(97_900.0)

    positions = await service.get_positions()
    assert positions[0].quantity == pytest.approx(15.0)
    assert positions[0].avg_cost == pytest.approx(150.0)  # unchanged by sell


async def test_sell_full_position_removes_it() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    await service.buy(SYMBOL, 10)

    await service.sell(SYMBOL, 10)

    assert await service.get_positions() == []


async def test_buy_insufficient_cash_raises() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))

    with pytest.raises(BusinessRuleError, match="Insufficient cash"):
        await service.buy(SYMBOL, 10_000)


async def test_failed_buy_does_not_change_cash() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))

    with pytest.raises(BusinessRuleError):
        await service.buy(SYMBOL, 10_000)

    valuation = await service.get_valuation()
    assert valuation.cash == pytest.approx(100_000.0)


async def test_sell_insufficient_shares_raises() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    await service.buy(SYMBOL, 5)

    with pytest.raises(BusinessRuleError, match="Insufficient shares"):
        await service.sell(SYMBOL, 10)


async def test_sell_with_no_position_raises_insufficient_shares() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))

    with pytest.raises(BusinessRuleError, match="Insufficient shares"):
        await service.sell(SYMBOL, 1)


async def test_trade_without_cached_price_raises_upstream_unavailable() -> None:
    service, _db, _cache = _service()

    with pytest.raises(UpstreamUnavailableError):
        await service.buy(SYMBOL, 1)


@pytest.mark.parametrize("quantity", [0, -1])
async def test_non_positive_quantity_raises_validation_error(quantity: float) -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))

    with pytest.raises(ValidationError):
        await service.buy(SYMBOL, quantity)


async def test_valuation_excludes_symbol_with_no_cached_price_from_total() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    await service.buy(SYMBOL, 10)

    cache.remove(SYMBOL)  # e.g. dropped from the watchlist after the buy

    valuation = await service.get_valuation()
    assert valuation.positions[0].current_price is None
    assert valuation.positions[0].market_value is None
    assert valuation.total_value == pytest.approx(valuation.cash)


async def test_get_trades_returns_newest_first() -> None:
    service, _db, cache = _service()
    cache.write(SYMBOL, 100.0, datetime.now(UTC))
    await service.buy(SYMBOL, 1)
    await service.buy(SYMBOL, 1)
    await service.sell(SYMBOL, 1)

    trades = await service.get_trades(10)

    assert [trade.side for trade in trades] == ["SELL", "BUY", "BUY"]
    assert trades[0].id > trades[1].id > trades[2].id
