from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol      TEXT PRIMARY KEY,
    added_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    symbol      TEXT PRIMARY KEY,
    quantity    REAL NOT NULL,
    avg_cost    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cash        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    condition   TEXT NOT NULL CHECK (condition IN ('ABOVE','BELOW')),
    threshold   REAL NOT NULL,
    triggered   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""

DEFAULT_CASH = 100_000.0

T = TypeVar("T")


class Database:
    """Thin SQLite wrapper. `lock` and `connection` are public — callers own the

    transaction boundary via `run()`, since a single request (e.g. a trade) is
    often several statements that must commit or roll back together.
    """

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.Lock()

    async def run(self, fn: Callable[[], T]) -> T:
        def _locked() -> T:
            with self.lock, self.connection:
                return fn()

        return await asyncio.to_thread(_locked)

    def init_schema(self, default_watchlist: list[str]) -> None:
        with self.lock, self.connection:
            self.connection.executescript(SCHEMA)
            seeded = self.connection.execute("SELECT 1 FROM account WHERE id = 1").fetchone()
            if seeded is None:
                self.connection.execute(
                    "INSERT INTO account (id, cash) VALUES (1, ?)", (DEFAULT_CASH,)
                )
                now = datetime.now(UTC).isoformat()
                self.connection.executemany(
                    "INSERT INTO watchlist (symbol, added_at) VALUES (?, ?)",
                    [(symbol, now) for symbol in default_watchlist],
                )

    def close(self) -> None:
        self.connection.close()

    # --- account --- (callers must hold `lock`, e.g. via `run()`)

    def get_cash(self) -> float:
        row = self.connection.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        cash: float = row["cash"]
        return float(cash)

    def set_cash(self, cash: float) -> None:
        self.connection.execute("UPDATE account SET cash = ? WHERE id = 1", (cash,))

    # --- positions ---

    def get_position(self, symbol: str) -> tuple[float, float] | None:
        row = self.connection.execute(
            "SELECT quantity, avg_cost FROM positions WHERE symbol = ?", (symbol,)
        ).fetchone()
        if row is None:
            return None
        return float(row["quantity"]), float(row["avg_cost"])

    def get_positions(self) -> list[tuple[str, float, float]]:
        rows = self.connection.execute(
            "SELECT symbol, quantity, avg_cost FROM positions ORDER BY symbol"
        ).fetchall()
        return [
            (str(row["symbol"]), float(row["quantity"]), float(row["avg_cost"])) for row in rows
        ]

    def upsert_position(self, symbol: str, quantity: float, avg_cost: float) -> None:
        self.connection.execute(
            """
            INSERT INTO positions (symbol, quantity, avg_cost) VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                quantity = excluded.quantity, avg_cost = excluded.avg_cost
            """,
            (symbol, quantity, avg_cost),
        )

    def delete_position(self, symbol: str) -> None:
        self.connection.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    # --- trades ---

    def insert_trade(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> tuple[int, str]:
        executed_at = datetime.now(UTC).isoformat()
        cursor = self.connection.execute(
            "INSERT INTO trades (symbol, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (symbol, side, quantity, price, executed_at),
        )
        trade_id = cursor.lastrowid
        assert trade_id is not None
        return int(trade_id), executed_at

    def get_trades(self, limit: int) -> list[tuple[int, str, str, float, float, str]]:
        rows = self.connection.execute(
            "SELECT id, symbol, side, quantity, price, executed_at FROM trades "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            (
                int(row["id"]),
                str(row["symbol"]),
                str(row["side"]),
                float(row["quantity"]),
                float(row["price"]),
                str(row["executed_at"]),
            )
            for row in rows
        ]

    # --- watchlist ---

    def get_watchlist(self) -> list[str]:
        # ORDER BY rowid, not added_at: seeded rows share one timestamp, so
        # added_at alone leaves ties in an unspecified order.
        rows = self.connection.execute(
            "SELECT symbol FROM watchlist ORDER BY rowid"
        ).fetchall()
        return [str(row["symbol"]) for row in rows]

    def add_watchlist_symbol(self, symbol: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO watchlist (symbol, added_at) VALUES (?, ?)",
            (symbol, datetime.now(UTC).isoformat()),
        )

    def remove_watchlist_symbol(self, symbol: str) -> bool:
        cursor = self.connection.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        return cursor.rowcount > 0

    # --- alerts ---

    def get_alerts(self) -> list[tuple[int, str, str, float, bool, str]]:
        rows = self.connection.execute(
            "SELECT id, symbol, condition, threshold, triggered, created_at "
            "FROM alerts ORDER BY id"
        ).fetchall()
        return [_row_to_alert_tuple(row) for row in rows]

    def get_active_alerts(self) -> list[tuple[int, str, str, float, bool, str]]:
        rows = self.connection.execute(
            "SELECT id, symbol, condition, threshold, triggered, created_at "
            "FROM alerts WHERE triggered = 0 ORDER BY id"
        ).fetchall()
        return [_row_to_alert_tuple(row) for row in rows]

    def insert_alert(self, symbol: str, condition: str, threshold: float) -> tuple[int, str]:
        created_at = datetime.now(UTC).isoformat()
        cursor = self.connection.execute(
            "INSERT INTO alerts (symbol, condition, threshold, triggered, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (symbol, condition, threshold, created_at),
        )
        alert_id = cursor.lastrowid
        assert alert_id is not None
        return int(alert_id), created_at

    def mark_alert_triggered(self, alert_id: int) -> None:
        self.connection.execute("UPDATE alerts SET triggered = 1 WHERE id = ?", (alert_id,))

    def delete_alert(self, alert_id: int) -> bool:
        cursor = self.connection.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        return cursor.rowcount > 0


def _row_to_alert_tuple(row: sqlite3.Row) -> tuple[int, str, str, float, bool, str]:
    return (
        int(row["id"]),
        str(row["symbol"]),
        str(row["condition"]),
        float(row["threshold"]),
        bool(row["triggered"]),
        str(row["created_at"]),
    )
