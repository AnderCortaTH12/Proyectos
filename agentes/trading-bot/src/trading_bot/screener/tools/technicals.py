"""Indicadores técnicos por ticker vía yfinance, con caché y backoff.

Los indicadores (RSI, MACD, SMA) se calculan con pandas/numpy puro, sin
dependencias externas (ni pandas-ta ni numba ni TA-Lib), para que el proyecto
funcione en cualquier versión de Python sin compilar nada.
"""
from typing import Optional

import pandas as pd

from ..models import TechnicalSnapshot
from .cache import DataCache
from .retry import with_backoff


@with_backoff(max_attempts=3)
def _download_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    import yfinance as yf  # import perezoso: solo necesario al descargar datos

    return yf.Ticker(ticker).history(period=period, auto_adjust=True)


# ---------- Indicadores (pandas/numpy puro) ----------
def sma(close: pd.Series, length: int) -> pd.Series:
    """Media móvil simple."""
    return close.rolling(window=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI con suavizado de Wilder (RMA), equivalente al RSI clásico."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    # Sin pérdidas -> avg_loss=0 -> rs=inf -> RSI=100 (comportamiento estándar).
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """Histograma del MACD (línea MACD menos su señal)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def _pct_return(close: pd.Series, days: int) -> Optional[float]:
    if len(close) <= days:
        return None
    past = close.iloc[-(days + 1)]
    last = close.iloc[-1]
    if past == 0:
        return None
    return float((last / past - 1.0) * 100.0)


def _last(series: pd.Series) -> Optional[float]:
    if series is None:
        return None
    clean = series.dropna()
    if clean.empty:
        return None
    return float(clean.iloc[-1])


def compute_technicals(ticker: str, hist: pd.DataFrame) -> TechnicalSnapshot:
    """Calcula RSI/MACD/SMA y retornos a partir de un histórico OHLCV."""
    if hist is None or hist.empty:
        return TechnicalSnapshot(ticker=ticker)

    close = hist["Close"].dropna()
    return TechnicalSnapshot(
        ticker=ticker,
        price=float(close.iloc[-1]),
        rsi_14=_last(rsi(close, length=14)),
        macd_hist=_last(macd_histogram(close)),
        sma_50=_last(sma(close, length=50)),
        sma_200=_last(sma(close, length=200)),
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
