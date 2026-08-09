from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.backtest.runner import run_ma_crossover
from app.backtest.strategies import MACrossoverParams
from app.market.models import Candle

BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def _candle(i: int, o: float, c: float) -> Candle:
    return Candle(t=BASE_TIME + timedelta(hours=i), o=o, h=max(o, c), l=min(o, c), c=c, v=1.0)


def test_known_candle_series_produces_known_trades_with_no_look_ahead() -> None:
    # Hand-verified with fast=2, slow=3 SMA over closes
    # [100, 100, 100, 150, 150, 50, 80]:
    #   signals = HOLD HOLD HOLD BUY HOLD SELL HOLD  (index 3 = BUY, index 5 = SELL)
    # A signal from candle i executes at candle i+1's OPEN. Opens are set far
    # away from the signal candle's own close (300, not 150; 80, not 50) so a
    # look-ahead bug — executing at the signal candle's own close instead —
    # would produce a different, wrong price and fail this test.
    candles = [
        _candle(0, o=100.0, c=100.0),
        _candle(1, o=100.0, c=100.0),
        _candle(2, o=100.0, c=100.0),
        _candle(3, o=200.0, c=150.0),  # BUY signal generated here (index 3)
        _candle(4, o=300.0, c=150.0),  # BUY executes here, at this open (300)
        _candle(5, o=100.0, c=50.0),  # SELL signal generated here (index 5)
        _candle(6, o=80.0, c=80.0),  # SELL executes here, at this open (80)
    ]

    result = run_ma_crossover(candles, MACrossoverParams(fast=2, slow=3), initial_cash=10_000.0)

    assert len(result.trades) == 2
    buy, sell = result.trades
    assert buy.side == "BUY"
    assert buy.price == pytest.approx(300.0)
    assert buy.t == candles[4].t
    assert sell.side == "SELL"
    assert sell.price == pytest.approx(80.0)
    assert sell.t == candles[6].t

    expected_quantity = 10_000.0 / 300.0
    assert buy.quantity == pytest.approx(expected_quantity)
    assert sell.quantity == pytest.approx(expected_quantity)

    assert len(result.equity_curve) == len(candles)
    assert result.equity_curve[0].value == pytest.approx(10_000.0)
    assert result.equity_curve[3].value == pytest.approx(10_000.0)  # still all cash
    assert result.equity_curve[4].value == pytest.approx(expected_quantity * 150.0)
    assert result.equity_curve[5].value == pytest.approx(expected_quantity * 50.0)
    final_cash = expected_quantity * 80.0
    assert result.equity_curve[6].value == pytest.approx(final_cash)

    assert result.metrics.trade_count == 2
    expected_return_pct = (final_cash - 10_000.0) / 10_000.0 * 100
    assert result.metrics.total_return_pct == pytest.approx(expected_return_pct)
    # Worst point is index 5 (equity ~1666.67 against a 10,000 peak).
    assert result.metrics.max_drawdown_pct == pytest.approx(
        (expected_quantity * 50.0 - 10_000.0) / 10_000.0 * 100
    )


def test_empty_candles_returns_empty_result() -> None:
    result = run_ma_crossover([], MACrossoverParams(fast=2, slow=3), initial_cash=10_000.0)

    assert result.trades == []
    assert result.equity_curve == []
    assert result.metrics.trade_count == 0
    assert result.metrics.total_return_pct == 0.0


def test_no_crossover_means_no_trades() -> None:
    candles = [_candle(i, 100.0, 100.0) for i in range(5)]

    result = run_ma_crossover(candles, MACrossoverParams(fast=2, slow=3), initial_cash=10_000.0)

    assert result.trades == []
    assert result.metrics.total_return_pct == pytest.approx(0.0)
    assert all(point.value == pytest.approx(10_000.0) for point in result.equity_curve)


def test_never_sells_without_holding_a_position() -> None:
    # A SELL signal with no open position must be a no-op, not a crash or a
    # short sale (out of scope per PLAN.md §2).
    candles = [
        _candle(0, 100.0, 150.0),
        _candle(1, 100.0, 100.0),
        _candle(2, 100.0, 50.0),  # SELL-crossing signal, but never bought
        _candle(3, 100.0, 100.0),
    ]

    result = run_ma_crossover(candles, MACrossoverParams(fast=1, slow=2), initial_cash=10_000.0)

    assert all(trade.side == "BUY" for trade in result.trades) or result.trades == []
