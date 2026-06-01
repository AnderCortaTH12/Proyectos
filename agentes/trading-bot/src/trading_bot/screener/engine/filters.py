"""Filtros duros: descartan candidatos que no cumplen los criterios obligatorios."""
from typing import Optional

from ..models import (
    Candidate,
    MomentumCondition,
    ScreenCriteria,
    SectorBenchmark,
    ValuationCondition,
)


def _valuation_value(cand: Candidate, metric: str) -> Optional[float]:
    return getattr(cand.fundamentals, metric, None)


def _momentum_value(cand: Candidate, indicator: str) -> Optional[float]:
    # sma_50_200_cross y price_vs_sma_200 son propiedades calculadas.
    return getattr(cand.technicals, indicator, None)


def _check_valuation(
    cand: Candidate, cond: ValuationCondition, benchmark: Optional[SectorBenchmark]
) -> tuple[bool, str]:
    value = _valuation_value(cand, cond.metric)
    if value is None:
        return False, f"sin dato de {cond.metric}"
    if cond.reference == "sector_median":
        if not benchmark or cond.metric not in benchmark.medians:
            return False, f"sin mediana sectorial de {cond.metric}"
        threshold = cond.value * benchmark.medians[cond.metric]
    else:
        threshold = cond.value
    ok = cond.comparator.compare(value, threshold)
    if ok:
        return True, ""
    return False, f"{cond.metric}={value:.2f} no cumple {cond.comparator.value}{threshold:.2f}"


def _check_momentum(cand: Candidate, cond: MomentumCondition) -> tuple[bool, str]:
    value = _momentum_value(cand, cond.indicator)
    if value is None:
        return False, f"sin dato de {cond.indicator}"
    ok = cond.comparator.compare(value, cond.value)
    if ok:
        return True, ""
    return False, f"{cond.indicator}={value:.2f} no cumple {cond.comparator.value}{cond.value:.2f}"


def passes_filters(
    cand: Candidate,
    criteria: ScreenCriteria,
    benchmark: Optional[SectorBenchmark],
) -> tuple[bool, str]:
    """Devuelve (True, "") si el candidato pasa todos los filtros, o (False, razón)."""
    # Sector
    if criteria.sectors and cand.sector not in criteria.sectors:
        return False, f"sector {cand.sector!r} fuera de {criteria.sectors}"

    # Market cap
    if criteria.market_cap and not criteria.market_cap.contains(cand.fundamentals.market_cap):
        return False, f"market cap {cand.fundamentals.market_cap:.0f} fuera de rango"

    # Valoración
    for cond in criteria.valuation:
        ok, reason = _check_valuation(cand, cond, benchmark)
        if not ok:
            return False, reason

    # Momentum
    for cond in criteria.momentum:
        ok, reason = _check_momentum(cand, cond)
        if not ok:
            return False, reason

    return True, ""
