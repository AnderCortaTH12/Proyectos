"""Caché de datos descargados en DuckDB con TTL (time-to-live)."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import duckdb


class DataCache:
    """Caché clave-valor (JSON) sobre DuckDB con expiración por TTL.

    Cada entrada tiene un namespace (p.ej. "fundamentals"), una clave (p.ej. el
    ticker) y un timestamp; al leer se comprueba que no haya superado el TTL.
    """

    def __init__(self, db_path: str, ttl_hours: int = 12) -> None:
        self.db_path = db_path
        self.ttl = timedelta(hours=ttl_hours)
        self._lock = threading.Lock()
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, duckdb.connect(self.db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    namespace VARCHAR,
                    key VARCHAR,
                    value VARCHAR,
                    stored_at TIMESTAMPTZ,
                    PRIMARY KEY (namespace, key)
                )
                """
            )

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Devuelve el valor cacheado si existe y no ha expirado; si no, None."""
        with self._lock, duckdb.connect(self.db_path) as con:
            row = con.execute(
                "SELECT value, stored_at FROM cache WHERE namespace = ? AND key = ?",
                [namespace, key],
            ).fetchone()
        if not row:
            return None
        value, stored_at = row
        if stored_at.tzinfo is None:
            stored_at = stored_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - stored_at > self.ttl:
            return None
        return json.loads(value)

    def set(self, namespace: str, key: str, value: Any) -> None:
        """Guarda (o reemplaza) un valor en la caché con el timestamp actual."""
        with self._lock, duckdb.connect(self.db_path) as con:
            con.execute(
                """
                INSERT INTO cache (namespace, key, value, stored_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (namespace, key)
                DO UPDATE SET value = excluded.value, stored_at = excluded.stored_at
                """,
                [namespace, key, json.dumps(value), datetime.now(timezone.utc)],
            )
