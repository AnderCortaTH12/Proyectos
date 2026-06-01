"""Indicadores técnicos por ticker (pandas-ta) vía yfinance, con caché y backoff."""
from typing import Optional

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from ..models import TechnicalSnapshot
from .cache import DataCache
from .retry import with_backoff


@with_backoff(max_attempts=3)
def _download_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    return yf.Ticker(ticker).history(period=period, auto_adjust=True)


def _pct_return(close: pd.Series, days: int) -> Optional[float]:
    if len(close) <= days:
        return None
    past = close.iloc[-(days + 1)]
    last = close.iloc[-1]
    if past == 0:
        return None
    return float((last / past - 1.0) * 100.0)


def compute_technicals(ticker: str, hist: pd.DataFrame) -> TechnicalSnapshot:
    """Calcula RSI/MACD/SMA y retornos a partir de un histórico OHLCV."""
    if hist is None or hist.empty:
        return TechnicalSnapshot(ticker=ticker)

    close = hist["Close"].dropna()
    rsi = ta.rsi(close, length=14)
    macd = ta.macd(close)
    sma50 = ta.sma(close, length=50)
    sma200 = ta.sma(close, length=200)

    def _last(series) -> Optional[float]:
        if series is None or len(series.dropna()) == 0:
            return None
        return float(series.dropna().iloc[-1])

    macd_hist = None
    if macd is not None and not macd.empty:
        hist_col = [c for c in macd.columns if c.startswith("MACDh")]
        if hist_col:
            macd_hist = _last(macd[hist_col[0]])

    return TechnicalSnapshot(
        ticker=ticker,
        price=float(close.iloc[-1]),
        rsi_14=_last(rsi),
        macd_hist=macd_hist,
        sma_50=_last(sma50),
        sma_200=_last(sma200),
        return_1m=_pct_return(close, 21),
        return_3m=_pct_return(close, 63),
        return_6m=_pct_return(close, 126),
    )


def get_technicals(ticker: str, cache: Optional[DataCache] = None) -> TechnicalSnapshot:
    """Devuelve un TechnicalSnapshot del ticker (cacheado)."""
    if cache:
        cached = cache.get("technicals", ticker)
        if cached:
            return TechnicalSnapshot(**cached)

    hist = _download_history(ticker)
    snap = compute_technicals(ticker, hist)
    if cache:
        cache.set("technicals", ticker, snap.model_dump())
    return snap
