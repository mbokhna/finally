from __future__ import annotations

from datetime import datetime

from app.db import Database
from app.errors import BusinessRuleError, UpstreamUnavailableError, ValidationError
from app.market.cache import PriceCache
from app.portfolio.models import PortfolioValuation, Position, PositionValuation, Trade


class PortfolioService:
    """Buy/sell, valuation, P&L. Average cost changes on buy, never on sell —

    a sell realises its gain/loss into cash instead.
    """

    def __init__(self, db: Database, cache: PriceCache, currency: str) -> None:
        self._db = db
        self._cache = cache
        self._currency = currency

    async def buy(self, symbol: str, quantity: float) -> tuple[Trade, float]:
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        price = self._current_price(symbol)

        def _op() -> tuple[Trade, float]:
            cash = self._db.get_cash()
            cost = quantity * price
            if cost > cash:
                raise BusinessRuleError(
                    f"Insufficient cash: need {cost:.2f} {self._currency}, "
                    f"have {cash:.2f} {self._currency}"
                )

            existing = self._db.get_position(symbol)
            if existing is None:
                new_quantity, new_avg_cost = quantity, price
            else:
                held_quantity, held_avg_cost = existing
                new_quantity = held_quantity + quantity
                new_avg_cost = (
                    held_quantity * held_avg_cost + quantity * price
                ) / new_quantity

            new_cash = cash - cost
            self._db.upsert_position(symbol, new_quantity, new_avg_cost)
            self._db.set_cash(new_cash)
            return self._record_trade(symbol, "BUY", quantity, price), new_cash

        return await self._db.run(_op)

    async def sell(self, symbol: str, quantity: float) -> tuple[Trade, float]:
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        price = self._current_price(symbol)

        def _op() -> tuple[Trade, float]:
            existing = self._db.get_position(symbol)
            held_quantity, avg_cost = existing if existing is not None else (0.0, 0.0)
            if quantity > held_quantity:
                raise BusinessRuleError(
                    f"Insufficient shares: need {quantity}, have {held_quantity}"
                )

            remaining = held_quantity - quantity
            if remaining <= 1e-9:
                self._db.delete_position(symbol)
            else:
                self._db.upsert_position(symbol, remaining, avg_cost)

            cash = self._db.get_cash()
            new_cash = cash + quantity * price
            self._db.set_cash(new_cash)
            return self._record_trade(symbol, "SELL", quantity, price), new_cash

        return await self._db.run(_op)

    async def get_positions(self) -> list[Position]:
        def _op() -> list[Position]:
            return [
                Position(symbol=symbol, quantity=quantity, avg_cost=avg_cost)
                for symbol, quantity, avg_cost in self._db.get_positions()
            ]

        return await self._db.run(_op)

    async def get_valuation(self) -> PortfolioValuation:
        def _op() -> tuple[float, list[tuple[str, float, float]]]:
            return self._db.get_cash(), self._db.get_positions()

        cash, rows = await self._db.run(_op)

        valuations: list[PositionValuation] = []
        total = cash
        for symbol, quantity, avg_cost in rows:
            update = self._cache.get(symbol)
            if update is None:
                valuations.append(
                    PositionValuation(
                        symbol=symbol,
                        quantity=quantity,
                        avg_cost=avg_cost,
                        current_price=None,
                        market_value=None,
                        unrealised_pnl=None,
                        unrealised_pnl_pct=None,
                    )
                )
                continue

            market_value = quantity * update.price
            cost_basis = quantity * avg_cost
            unrealised_pnl = market_value - cost_basis
            unrealised_pnl_pct = (unrealised_pnl / cost_basis * 100) if cost_basis else 0.0
            total += market_value
            valuations.append(
                PositionValuation(
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    current_price=update.price,
                    market_value=market_value,
                    unrealised_pnl=unrealised_pnl,
                    unrealised_pnl_pct=unrealised_pnl_pct,
                )
            )

        return PortfolioValuation(
            cash=cash, positions=valuations, total_value=total, currency=self._currency
        )

    async def get_trades(self, limit: int) -> list[Trade]:
        def _op() -> list[Trade]:
            return [
                Trade(
                    id=trade_id,
                    symbol=symbol,
                    side="BUY" if side == "BUY" else "SELL",
                    quantity=quantity,
                    price=price,
                    executed_at=datetime.fromisoformat(executed_at),
                )
                for trade_id, symbol, side, quantity, price, executed_at in self._db.get_trades(
                    limit
                )
            ]

        return await self._db.run(_op)

    def _current_price(self, symbol: str) -> float:
        update = self._cache.get(symbol)
        if update is None:
            raise UpstreamUnavailableError(f"No price cached for {symbol} — cannot trade")
        return update.price

    def _record_trade(self, symbol: str, side: str, quantity: float, price: float) -> Trade:
        trade_id, executed_at = self._db.insert_trade(symbol, side, quantity, price)
        return Trade(
            id=trade_id,
            symbol=symbol,
            side="BUY" if side == "BUY" else "SELL",
            quantity=quantity,
            price=price,
            executed_at=datetime.fromisoformat(executed_at),
        )
