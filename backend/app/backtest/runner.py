from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.backtest.strategies import MACrossoverParams, ma_crossover_signals
from app.market.models import Candle

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class BacktestTrade:
    t: datetime
    side: Side
    price: float
    quantity: float


@dataclass(frozen=True)
class EquityPoint:
    t: datetime
    value: float


@dataclass(frozen=True)
class BacktestMetrics:
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int


@dataclass(frozen=True)
class BacktestResult:
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    metrics: BacktestMetrics


def run_ma_crossover(
    candles: list[Candle], params: MACrossoverParams, initial_cash: float
) -> BacktestResult:
    if not candles:
        return BacktestResult(
            trades=[],
            equity_curve=[],
            metrics=BacktestMetrics(total_return_pct=0.0, max_drawdown_pct=0.0, trade_count=0),
        )

    signals = ma_crossover_signals(candles, params)

    cash = initial_cash
    quantity = 0.0
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []

    for i, candle in enumerate(candles):
        # A signal from candle i-1 executes at candle i's open, never at the
        # close of the candle that produced it — that close wasn't known yet
        # at decision time in a real feed. This is the one rule that keeps a
        # backtest honest.
        if i > 0:
            signal = signals[i - 1]
            if signal == "BUY" and quantity == 0.0:
                quantity = cash / candle.o
                cash = 0.0
                trades.append(
                    BacktestTrade(t=candle.t, side="BUY", price=candle.o, quantity=quantity)
                )
            elif signal == "SELL" and quantity > 0.0:
                cash = quantity * candle.o
                trades.append(
                    BacktestTrade(t=candle.t, side="SELL", price=candle.o, quantity=quantity)
                )
                quantity = 0.0

        equity_curve.append(EquityPoint(t=candle.t, value=cash + quantity * candle.c))

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        metrics=_metrics(equity_curve, initial_cash, len(trades)),
    )


def _metrics(
    equity_curve: list[EquityPoint], initial_cash: float, trade_count: int
) -> BacktestMetrics:
    final_equity = equity_curve[-1].value if equity_curve else initial_cash
    total_return_pct = (final_equity - initial_cash) / initial_cash * 100

    peak = initial_cash
    max_drawdown_pct = 0.0
    for point in equity_curve:
        peak = max(peak, point.value)
        max_drawdown_pct = min(max_drawdown_pct, (point.value - peak) / peak * 100)

    return BacktestMetrics(
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=trade_count,
    )
