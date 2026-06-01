"""Universo de inversión: constituyentes del S&P 500 (Wikipedia), cacheado."""
from typing import Optional

import pandas as pd

from .cache import DataCache
from .retry import with_backoff

WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Lista mínima de respaldo si no hay red (para que la demo no se caiga del todo).
_FALLBACK = [
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Information Technology"},
    {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Information Technology"},
    {"ticker": "NVDA", "name": "NVIDIA Corp.", "sector": "Information Technology"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financials"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Health Care"},
]


@with_backoff(max_attempts=3)
def _download_sp500() -> list[dict]:
    tables = pd.read_html(WIKI_SP500)
    df = tables[0]
    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "ticker": str(row["Symbol"]).replace(".", "-"),
                "name": str(row["Security"]),
                "sector": str(row["GICS Sector"]),
            }
        )
    return out


def get_universe(cache: Optional[DataCache] = None) -> list[dict]:
    """Devuelve los constituyentes del S&P 500 (ticker, name, sector), con caché."""
    if cache:
        cached = cache.get("universe", "sp500")
        if cached:
            return cached
    try:
        data = _download_sp500()
    except Exception:
        data = _FALLBACK
    if cache and data:
        cache.set("universe", "sp500", data)
    return data
