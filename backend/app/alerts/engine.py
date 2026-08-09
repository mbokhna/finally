from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import datetime

from app.alerts.models import Alert, Condition
from app.db import Database
from app.market.cache import PriceCache

POLL_SECONDS = 0.1


def _row_to_alert(row: tuple[int, str, str, float, bool, str]) -> Alert:
    alert_id, symbol, condition, threshold, triggered, created_at = row
    condition_literal: Condition = "ABOVE" if condition == "ABOVE" else "BELOW"
    return Alert(
        id=alert_id,
        symbol=symbol,
        condition=condition_literal,
        threshold=threshold,
        triggered=triggered,
        created_at=datetime.fromisoformat(created_at),
    )


def _crossed(condition: Condition, threshold: float, price: float) -> bool:
    if condition == "ABOVE":
        return price >= threshold
    return price <= threshold


class AlertEngine:
    """Owns alert CRUD and evaluates active alerts against the price cache.

    Polls the cache's version counter the same way the SSE price stream does,
    so a fire happens within one poll cycle of the price crossing its
    threshold. Fires once: a triggered alert is excluded from evaluation until
    it is deleted and recreated.
    """

    def __init__(self, db: Database, cache: PriceCache) -> None:
        self._db = db
        self._cache = cache
        self._task: asyncio.Task[None] | None = None
        self._subscribers: list[asyncio.Queue[Alert]] = []
        self._last_seen_version = -1

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def create(self, symbol: str, condition: Condition, threshold: float) -> Alert:
        def _op() -> tuple[int, str]:
            return self._db.insert_alert(symbol, condition, threshold)

        alert_id, created_at = await self._db.run(_op)
        return Alert(
            id=alert_id,
            symbol=symbol,
            condition=condition,
            threshold=threshold,
            triggered=False,
            created_at=datetime.fromisoformat(created_at),
        )

    async def list_all(self) -> list[Alert]:
        rows = await self._db.run(self._db.get_alerts)
        return [_row_to_alert(row) for row in rows]

    async def delete(self, alert_id: int) -> bool:
        return await self._db.run(lambda: self._db.delete_alert(alert_id))

    async def events(self) -> AsyncIterator[Alert]:
        """Yields alerts as they fire. Each caller gets every fire — a fan-out,

        not a work queue — since more than one browser tab may be listening.
        """
        queue: asyncio.Queue[Alert] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.remove(queue)

    async def _run(self) -> None:
        while True:
            snapshot, version = self._cache.snapshot()
            if version != self._last_seen_version:
                self._last_seen_version = version
                await self._evaluate({update.symbol: update.price for update in snapshot})
            await asyncio.sleep(POLL_SECONDS)

    async def _evaluate(self, prices: dict[str, float]) -> None:
        def _op() -> list[Alert]:
            fired: list[Alert] = []
            for row in self._db.get_active_alerts():
                alert = _row_to_alert(row)
                price = prices.get(alert.symbol)
                if price is None:
                    continue
                if _crossed(alert.condition, alert.threshold, price):
                    self._db.mark_alert_triggered(alert.id)
                    fired.append(
                        Alert(
                            id=alert.id,
                            symbol=alert.symbol,
                            condition=alert.condition,
                            threshold=alert.threshold,
                            triggered=True,
                            created_at=alert.created_at,
                        )
                    )
            return fired

        fired = await self._db.run(_op)
        for alert in fired:
            for queue in self._subscribers:
                await queue.put(alert)
