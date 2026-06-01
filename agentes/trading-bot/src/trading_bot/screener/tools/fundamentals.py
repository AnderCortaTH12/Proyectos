"""Datos fundamentales por ticker vía yfinance, con caché y backoff."""
from typing import Optional

import yfinance as yf

from ..models import FundamentalSnapshot
from .cache import DataCache
from .retry import with_backoff


@with_backoff(max_attempts=3)
def _download_info(ticker: str) -> dict:
    return yf.Ticker(ticker).info or {}


def _safe(value) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


def get_fundamentals(
    ticker: str,
    name: str = "",
    sector: str = "",
    cache: Optional[DataCache] = None,
) -> FundamentalSnapshot:
    """Devuelve un FundamentalSnapshot del ticker (cacheado)."""
    if cache:
        cached = cache.get("fundamentals", ticker)
        if cached:
            return FundamentalSnapshot(**cached)

    info = _download_info(ticker)
    snap = FundamentalSnapshot(
        ticker=ticker,
        name=name or str(info.get("shortName", "")),
        sector=sector or str(info.get("sector", "")),
        market_cap=_safe(info.get("marketCap")) or 0.0,
        pe_ratio=_safe(info.get("trailingPE")),
        forward_pe=_safe(info.get("forwardPE")),
        pb_ratio=_safe(info.get("priceToBook")),
        ev_ebitda=_safe(info.get("enterpriseToEbitda")),
        price_to_sales=_safe(info.get("priceToSalesTrailing12Months")),
        dividend_yield=_safe(info.get("dividendYield")),
        peg_ratio=_safe(info.get("trailingPegRatio")),
        roe=_safe(info.get("returnOnEquity")),
        debt_to_equity=_safe(info.get("debtToEquity")),
        profit_margin=_safe(info.get("profitMargins")),
    )
    if cache:
        cache.set("fundamentals", ticker, snap.model_dump())
    return snap
