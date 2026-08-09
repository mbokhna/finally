from __future__ import annotations

from datetime import UTC, datetime

from app.ai.context import build_context
from app.alerts.models import Alert
from app.market.models import PriceUpdate
from app.portfolio.models import PortfolioValuation, PositionValuation, Trade

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def test_build_context_with_empty_portfolio() -> None:
    valuation = PortfolioValuation(
        cash=100_000.0, positions=[], total_value=100_000.0, currency="PLN"
    )

    context = build_context(valuation, prices=[], trades=[], alerts=[])

    assert "CASH: 100000.00 PLN" in context
    assert "TOTAL VALUE: 100000.00 PLN" in context
    assert "POSITIONS:\n(none)" in context
    assert "PRICES (watchlist):\n(none)" in context
    assert "RECENT TRADES (last 10):\n(none)" in context
    assert "ACTIVE ALERTS:\n(none)" in context


def test_build_context_includes_position_details() -> None:
    valuation = PortfolioValuation(
        cash=90_000.0,
        positions=[
            PositionValuation(
                symbol="CRYPTO:BTCUSDT",
                quantity=0.1,
                avg_cost=78_000.0,
                current_price=79_411.2,
                market_value=7941.12,
                unrealised_pnl=141.12,
                unrealised_pnl_pct=1.81,
            )
        ],
        total_value=97_941.12,
        currency="PLN",
    )

    context = build_context(valuation, prices=[], trades=[], alerts=[])

    assert "CRYPTO:BTCUSDT: qty=0.1 avg_cost=78000.00 price=79411.20 pnl=+141.12" in context


def test_build_context_marks_position_with_no_cached_price() -> None:
    valuation = PortfolioValuation(
        cash=90_000.0,
        positions=[
            PositionValuation(
                symbol="GPW:PKN",
                quantity=5.0,
                avg_cost=64.0,
                current_price=None,
                market_value=None,
                unrealised_pnl=None,
                unrealised_pnl_pct=None,
            )
        ],
        total_value=90_000.0,
        currency="PLN",
    )

    context = build_context(valuation, prices=[], trades=[], alerts=[])

    assert "price=N/A pnl=N/A" in context


def test_build_context_includes_prices_sorted_by_symbol() -> None:
    valuation = PortfolioValuation(
        cash=100_000.0, positions=[], total_value=100_000.0, currency="PLN"
    )
    prices = [
        PriceUpdate(symbol="GPW:PKN", price=65.2, previous_price=64.9, timestamp=NOW),
        PriceUpdate(symbol="CRYPTO:BTCUSDT", price=79411.2, previous_price=79380.1, timestamp=NOW),
    ]

    context = build_context(valuation, prices=prices, trades=[], alerts=[])

    prices_section = context.split("PRICES (watchlist):\n")[1].split("\n\n")[0]
    assert prices_section == "CRYPTO:BTCUSDT: 79411.2000\nGPW:PKN: 65.2000"


def test_build_context_includes_trades_and_alerts() -> None:
    valuation = PortfolioValuation(
        cash=100_000.0, positions=[], total_value=100_000.0, currency="PLN"
    )
    trades = [
        Trade(
            id=1, symbol="CRYPTO:BTCUSDT", side="BUY", quantity=0.05, price=79411.2, executed_at=NOW
        )
    ]
    alerts = [
        Alert(
            id=1,
            symbol="CRYPTO:BTCUSDT",
            condition="ABOVE",
            threshold=80000.0,
            triggered=False,
            created_at=NOW,
        ),
        Alert(
            id=2,
            symbol="GPW:PKN",
            condition="BELOW",
            threshold=60.0,
            triggered=True,
            created_at=NOW,
        ),
    ]

    context = build_context(valuation, prices=[], trades=trades, alerts=alerts)

    assert "BUY 0.05 CRYPTO:BTCUSDT @ 79411.20" in context
    assert "CRYPTO:BTCUSDT ABOVE 80000.0" in context
    assert "GPW:PKN BELOW 60.0 [fired]" in context
