"""Logging estructurado (JSON) con timestamp para auditar las acciones del bot."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON con timestamp ISO-8601 UTC."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Campos extra arbitrarios (p.ej. ticker, rationale, order_id).
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "trading_bot") -> logging.Logger:
    """Devuelve un logger configurado con salida JSON a stdout (idempotente)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, msg: str, **fields) -> None:
    """Loguea un evento con campos estructurados extra (timestamp + rationale, etc.)."""
    logger.info(msg, extra={"extra_fields": fields})
