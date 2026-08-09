from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.backtest.strategies import MACrossoverParams, ma_crossover_signals, moving_average
from app.market.models import Candle


def _candle(close: float, open_: float | None = None) -> Candle:
    o = open_ if open_ is not None else close
    return Candle(t=datetime.now(UTC), o=o, h=max(o, close), l=min(o, close), c=close, v=1.0)


def test_moving_average_is_none_until_window_is_full() -> None:
    result = moving_average([10.0, 20.0, 30.0, 40.0], window=3)

    assert result == [None, None, pytest.approx(20.0), pytest.approx(30.0)]


def test_moving_average_window_one_equals_the_series() -> None:
    result = moving_average([1.0, 2.0, 3.0], window=1)

    assert result == [pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0)]


def test_signals_are_hold_until_both_averages_are_available() -> None:
    candles = [_candle(c) for c in [100.0, 100.0]]

    signals = ma_crossover_signals(candles, MACrossoverParams(fast=1, slow=3))

    assert signals == ["HOLD", "HOLD"]


def test_buy_then_sell_on_crossover() -> None:
    # fast=2, slow=3 SMA over these closes: crosses up once, then down once.
    closes = [100.0, 100.0, 100.0, 150.0, 150.0, 50.0, 80.0]
    candles = [_candle(c) for c in closes]

    signals = ma_crossover_signals(candles, MACrossoverParams(fast=2, slow=3))

    assert signals == ["HOLD", "HOLD", "HOLD", "BUY", "HOLD", "SELL", "HOLD"]


def test_no_second_buy_signal_while_already_long() -> None:
    closes = [100.0, 100.0, 100.0, 200.0, 300.0, 400.0]
    candles = [_candle(c) for c in closes]

    signals = ma_crossover_signals(candles, MACrossoverParams(fast=2, slow=3))

    assert signals.count("BUY") == 1
