"""Puntuación ponderada de candidatos en escala 0–10.

Tres sub-puntuaciones (valuation, momentum, quality), combinadas con los pesos
de ScreenCriteria. Las heurísticas son transparentes y deliberadamente simples:
es un proyecto demostrativo, no un modelo de inversión.
"""
from typing import Optional

from ..models import (
    Candidate,
    ScoredCandidate,
    ScoreWeights,
    SectorBenchmark,
)

# Métricas de valoración donde "más barato que la mediana" puntúa alto.
_CHEAPER_IS_BETTER = ["pe_ratio", "forward_pe", "pb_ratio", "ev_ebitda", "price_to_sales", "peg_ratio"]


def _clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, x))


def _valuation_score(cand: Candidate, benchmark: Optional[SectorBenchmark]) -> float:
    """5 = en la mediana del sector; >5 más barato; <5 más caro. Promedio de métricas."""
    if not benchmark or not benchmark.medians:
        return 5.0
    scores: list[float] = []
    for metric in _CHEAPER_IS_BETTER:
        value = getattr(cand.fundamentals, metric, None)
        median = benchmark.medians.get(metric)
        if value is None or not median or value <= 0:
            continue
        ratio = median / value  # >1 si más barato que la mediana
        scores.append(_clamp(5.0 * ratio))
    return sum(scores) / len(scores) if scores else 5.0


def _momentum_score(cand: Candidate) -> float:
    """Combina RSI, retornos, cruce de medias y precio vs SMA200."""
    t = cand.technicals
    parts: list[float] = []

    if t.rsi_14 is not None:
        # Óptimo en torno a 60; penaliza sobrecompra (>75) y debilidad (<40).
        parts.append(_clamp(10.0 - abs(t.rsi_14 - 60.0) / 4.0))
    if t.return_3m is not None:
        parts.append(_clamp(5.0 + t.return_3m / 4.0))
    if t.return_6m is not None:
        parts.append(_clamp(5.0 + t.return_6m / 6.0))
    if t.sma_50_200_cross is not None:
        parts.append(8.0 if t.sma_50_200_cross == 1.0 else 3.0)
    if t.price_vs_sma_200 is not None:
        parts.append(7.0 if t.price_vs_sma_200 == 1.0 else 3.0)

    return sum(parts) / len(parts) if parts else 5.0


def _quality_score(cand: Candidate) -> float:
    """ROE y márgenes altos suman; mucha deuda resta."""
    f = cand.fundamentals
    parts: list[float] = []

    if f.roe is not None:
        parts.append(_clamp(f.roe * 100.0 / 3.0))  # ROE 0.30 -> 10
    if f.profit_margin is not None:
        parts.append(_clamp(f.profit_margin * 100.0 / 3.0))
    if f.debt_to_equity is not None:
        # debtToEquity de yfinance viene en %, p.ej. 150 = 1.5x.
        parts.append(_clamp(10.0 - f.debt_to_equity / 30.0))

    return sum(parts) / len(parts) if parts else 5.0


def score_candidate(
    cand: Candidate,
    weights: ScoreWeights,
    benchmark: Optional[SectorBenchmark],
) -> ScoredCandidate:
    """Calcula las sub-puntuaciones y la puntuación total ponderada (0–10)."""
    sub = {
        "valuation": round(_valuation_score(cand, benchmark), 2),
        "momentum": round(_momentum_score(cand), 2),
        "quality": round(_quality_score(cand), 2),
    }
    total = (
        sub["valuation"] * weights.valuation
        + sub["momentum"] * weights.momentum
        + sub["quality"] * weights.quality
    )
    return ScoredCandidate(candidate=cand, score=round(_clamp(total), 2), sub_scores=sub)
