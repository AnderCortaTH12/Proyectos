"""Tests de los indicadores técnicos nativos (pandas puro, sin red ni pandas-ta)."""
import pandas as pd

from trading_bot.screener.tools.technicals import compute_technicals, rsi, sma


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype="float64")


def test_sma_valor_conocido():
    s = _series([1, 2, 3, 4, 5])
    assert sma(s, 3).iloc[-1] == 4.0  # media de 3,4,5


def test_rsi_100_si_solo_sube():
    # Serie estrictamente creciente -> sin pérdidas -> RSI tiende a 100.
    s = _series([float(i) for i in range(1, 40)])
    val = rsi(s, length=14).iloc[-1]
    assert val > 99.0


def test_rsi_en_rango():
    s = _series([10, 11, 10.5, 12, 11.8, 13, 12.5, 14, 13.2, 15, 14.1, 16, 15, 17, 16.2, 18])
    val = rsi(s, length=14).iloc[-1]
    assert 0.0 <= val <= 100.0


def test_compute_technicals_desde_dataframe():
    closes = [100 + i * 0.5 for i in range(220)]  # tendencia alcista
    df = pd.DataFrame({"Close": closes})
    snap = compute_technicals("TEST", df)
    assert snap.price == closes[-1]
    assert snap.sma_50 is not None and snap.sma_200 is not None
    assert snap.sma_50 > snap.sma_200            # cruce dorado en tendencia alcista
    assert snap.sma_50_200_cross == 1.0
    assert snap.return_3m is not None


def test_compute_technicals_vacio():
    snap = compute_technicals("TEST", pd.DataFrame({"Close": []}))
    assert snap.ticker == "TEST"
    assert snap.rsi_14 is None
