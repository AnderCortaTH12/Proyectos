"""Benchmarks por sector: medianas de métricas de valoración."""
import statistics
from collections.abc import Iterable

from ..models import FundamentalSnapshot, SectorBenchmark

# Métricas sobre las que calculamos medianas sectoriales.
_METRICS = ["pe_ratio", "forward_pe", "pb_ratio", "ev_ebitda", "price_to_sales", "peg_ratio"]


def compute_sector_benchmarks(
    snapshots: Iterable[FundamentalSnapshot],
) -> dict[str, SectorBenchmark]:
    """Agrupa por sector y calcula la mediana de cada métrica (ignorando None)."""
    by_sector: dict[str, list[FundamentalSnapshot]] = {}
    for s in snapshots:
        if s.sector:
            by_sector.setdefault(s.sector, []).append(s)

    result: dict[str, SectorBenchmark] = {}
    for sector, items in by_sector.items():
        medians: dict[str, float] = {}
        for metric in _METRICS:
            values = [getattr(s, metric) for s in items if getattr(s, metric) is not None]
            if values:
                medians[metric] = float(statistics.median(values))
        result[sector] = SectorBenchmark(sector=sector, medians=medians)
    return result


def get_sector_benchmarks(
    sector: str, snapshots: Iterable[FundamentalSnapshot]
) -> SectorBenchmark:
    """Benchmark de un sector concreto (vacío si no hay datos)."""
    return compute_sector_benchmarks(snapshots).get(
        sector, SectorBenchmark(sector=sector, medians={})
    )
