from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.market.models import Candle

Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class MACrossoverParams:
    fast: int
    slow: int


def moving_average(values: list[float], window: int) -> list[float | None]:
    """Simple moving average; None wherever there isn't `window` history yet."""
    result: list[float | None] = []
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= window:
            total -= values[i - window]
        result.append(total / window if i >= window - 1 else None)
    return result


def ma_crossover_signals(candles: list[Candle], params: MACrossoverParams) -> list[Signal]:
    """One signal per candle index, from that candle's own close.

    Just the signal — the runner decides when it's actually executed. Computing
    it here from candle i's close and executing it at candle i's own price would
    be look-ahead bias.
    """
    closes = [candle.c for candle in candles]
    fast_ma = moving_average(closes, params.fast)
    slow_ma = moving_average(closes, params.slow)

    signals: list[Signal] = []
    position_is_long = False
    for fast_value, slow_value in zip(fast_ma, slow_ma, strict=True):
        if fast_value is None or slow_value is None:
            signals.append("HOLD")
        elif fast_value > slow_value and not position_is_long:
            signals.append("BUY")
            position_is_long = True
        elif fast_value < slow_value and position_is_long:
            signals.append("SELL")
            position_is_long = False
        else:
            signals.append("HOLD")
    return signals
