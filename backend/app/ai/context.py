from __future__ import annotations

from app.alerts.models import Alert
from app.market.models import PriceUpdate
from app.portfolio.models import PortfolioValuation, Trade


def build_context(
    valuation: PortfolioValuation,
    prices: list[PriceUpdate],
    trades: list[Trade],
    alerts: list[Alert],
) -> str:
    """Compact plain-text context, assembled fresh per request. Tables as plain

    text, not JSON: fewer tokens for a free-tier model, and models read them fine.
    """
    return (
        f"CASH: {valuation.cash:.2f} {valuation.currency}\n"
        f"TOTAL VALUE: {valuation.total_value:.2f} {valuation.currency}\n"
        "\n"
        "POSITIONS:\n"
        f"{_positions_table(valuation)}\n"
        "\n"
        "PRICES (watchlist):\n"
        f"{_prices_table(prices)}\n"
        "\n"
        "RECENT TRADES (last 10):\n"
        f"{_trades_table(trades)}\n"
        "\n"
        "ACTIVE ALERTS:\n"
        f"{_alerts_table(alerts)}"
    )


def _positions_table(valuation: PortfolioValuation) -> str:
    if not valuation.positions:
        return "(none)"
    lines = []
    for position in valuation.positions:
        price = f"{position.current_price:.2f}" if position.current_price is not None else "N/A"
        pnl = f"{position.unrealised_pnl:+.2f}" if position.unrealised_pnl is not None else "N/A"
        lines.append(
            f"{position.symbol}: qty={position.quantity} avg_cost={position.avg_cost:.2f} "
            f"price={price} pnl={pnl}"
        )
    return "\n".join(lines)


def _prices_table(prices: list[PriceUpdate]) -> str:
    if not prices:
        return "(none)"
    return "\n".join(f"{p.symbol}: {p.price:.4f}" for p in sorted(prices, key=lambda p: p.symbol))


def _trades_table(trades: list[Trade]) -> str:
    if not trades:
        return "(none)"
    return "\n".join(
        f"{trade.executed_at.isoformat()} {trade.side} {trade.quantity} {trade.symbol} "
        f"@ {trade.price:.2f}"
        for trade in trades
    )


def _alerts_table(alerts: list[Alert]) -> str:
    if not alerts:
        return "(none)"
    return "\n".join(
        f"{alert.symbol} {alert.condition} {alert.threshold}"
        + (" [fired]" if alert.triggered else "")
        for alert in alerts
    )
