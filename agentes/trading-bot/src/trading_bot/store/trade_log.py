"""Registro persistente en DuckDB: ejecuciones del bot, órdenes y equity curve."""
import os
import threading
from datetime import datetime, timezone

import duckdb

from ..models import BotRunRecord, EquityPoint, Order


class TradeLog:
    """Almacena y consulta el histórico del bot (auditable)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, duckdb.connect(self.db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id VARCHAR PRIMARY KEY, ts TIMESTAMPTZ, query VARCHAR, payload VARCHAR
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id VARCHAR, client_order_id VARCHAR PRIMARY KEY, ticker VARCHAR,
                    side VARCHAR, qty DOUBLE, status VARCHAR, ts TIMESTAMPTZ, rationale VARCHAR
                );
                CREATE TABLE IF NOT EXISTS equity (
                    ts TIMESTAMPTZ PRIMARY KEY, equity DOUBLE
                );
                """
            )

    def record_run(self, record: BotRunRecord) -> None:
        """Guarda una ejecución completa y sus órdenes."""
        with self._lock, duckdb.connect(self.db_path) as con:
            con.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?)",
                [record.run_id, record.timestamp, record.query, record.model_dump_json()],
            )
            for o in record.orders_placed:
                con.execute(
                    "INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [o.id, o.client_order_id, o.ticker, o.side.value, o.qty,
                     o.status.value, o.submitted_at, o.rationale],
                )

    def add_equity_point(self, point: EquityPoint) -> None:
        with self._lock, duckdb.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO equity VALUES (?, ?)", [point.timestamp, point.equity])

    def get_orders(self, limit: int = 200) -> list[Order]:
        with self._lock, duckdb.connect(self.db_path) as con:
            rows = con.execute(
                "SELECT id, client_order_id, ticker, side, qty, status, ts, rationale "
                "FROM orders ORDER BY ts DESC LIMIT ?",
                [limit],
            ).fetchall()
        return [
            Order(
                id=r[0], client_order_id=r[1], ticker=r[2], side=r[3], qty=r[4],
                status=r[5], submitted_at=r[6] or datetime.now(timezone.utc), rationale=r[7] or "",
            )
            for r in rows
        ]

    def get_equity_curve(self) -> list[EquityPoint]:
        with self._lock, duckdb.connect(self.db_path) as con:
            rows = con.execute("SELECT ts, equity FROM equity ORDER BY ts ASC").fetchall()
        return [EquityPoint(timestamp=r[0], equity=r[1]) for r in rows]

    def get_runs(self, limit: int = 50) -> list[BotRunRecord]:
        with self._lock, duckdb.connect(self.db_path) as con:
            rows = con.execute(
                "SELECT payload FROM runs ORDER BY ts DESC LIMIT ?", [limit]
            ).fetchall()
        return [BotRunRecord.model_validate_json(r[0]) for r in rows]
