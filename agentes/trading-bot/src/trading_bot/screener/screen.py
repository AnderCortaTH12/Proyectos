"""Orquestador del screener: une planner, tools, engine y reasoning en un ScreenResult."""
import asyncio
from typing import Optional

from ..telemetry import TokenUsage
from .engine.filters import passes_filters
from .engine.scoring import score_candidate
from .models import (
    Candidate,
    RejectedCandidate,
    ScreenCriteria,
    ScreenResult,
    TraceStep,
)
from .parser.planner import plan
from .reasoning.reasoner import justify
from .tools.benchmarks import compute_sector_benchmarks
from .tools.cache import DataCache
from .tools.fundamentals import get_fundamentals
from .tools.technicals import get_technicals
from .tools.universe import get_universe

# Tope de tickers a descargar por ejecución (mantiene la demo rápida y barata).
MAX_UNIVERSE = 80


def _criteria_summary(c: ScreenCriteria) -> str:
    parts = [f"consulta='{c.raw_query}'"]
    if c.sectors:
        parts.append(f"sectores={c.sectors}")
    if c.market_cap:
        parts.append(f"market_cap=[{c.market_cap.min_usd},{c.market_cap.max_usd}]")
    if c.valuation:
        parts.append(f"valoración={[v.model_dump() for v in c.valuation]}")
    if c.momentum:
        parts.append(f"momentum={[m.model_dump() for m in c.momentum]}")
    return "; ".join(parts)


async def _download_candidate(row: dict, cache: Optional[DataCache]) -> Candidate:
    """Descarga (en hilos) fundamentales y técnicos de un ticker en paralelo."""
    ticker = row["ticker"]
    fundamentals, technicals = await asyncio.gather(
        asyncio.to_thread(get_fundamentals, ticker, row.get("name", ""), row.get("sector", ""), cache),
        asyncio.to_thread(get_technicals, ticker, cache),
    )
    return Candidate(
        ticker=ticker,
        name=row.get("name", ""),
        sector=row.get("sector", ""),
        fundamentals=fundamentals,
        technicals=technicals,
    )


async def _download_all(rows: list[dict], cache: Optional[DataCache]) -> list[Candidate]:
    sem = asyncio.Semaphore(8)  # límite de concurrencia para no saturar la API

    async def _guarded(row: dict) -> Optional[Candidate]:
        async with sem:
            try:
                return await _download_candidate(row, cache)
            except Exception:
                return None

    results = await asyncio.gather(*[_guarded(r) for r in rows])
    return [c for c in results if c is not None]


def run_screen(
    query: str,
    cache: Optional[DataCache] = None,
    client=None,
    planner_model: str = "claude-haiku-4-5",
    reasoner_model: str = "claude-sonnet-4-6",
    usage: Optional[TokenUsage] = None,
) -> ScreenResult:
    """Ejecuta el pipeline completo de screening para una consulta NL."""
    usage = usage or TokenUsage()
    trace: list[TraceStep] = []

    # 1) Planner: NL -> criterios
    criteria = plan(query, client=client, model=planner_model, usage=usage)
    trace.append(TraceStep(name="criterios_extraidos", detail=criteria.model_dump(mode="json")))

    # 2) Universo (filtrado por sector si procede, y capado)
    universe = get_universe(cache)
    if criteria.sectors:
        universe = [u for u in universe if u["sector"] in criteria.sectors]
    universe = universe[:MAX_UNIVERSE]
    trace.append(TraceStep(name="universo", detail={"n_tickers": len(universe)}))

    # 3) Descarga en paralelo
    candidates = asyncio.run(_download_all(universe, cache))
    trace.append(TraceStep(name="datos_descargados", detail={"n_candidatos": len(candidates)}))

    # 4) Benchmarks sectoriales (medianas sobre lo descargado)
    benchmarks = compute_sector_benchmarks([c.fundamentals for c in candidates])

    # 5) Filtros duros
    rejected: list[RejectedCandidate] = []
    passed: list[Candidate] = []
    for cand in candidates:
        ok, reason = passes_filters(cand, criteria, benchmarks.get(cand.sector))
        if ok:
            passed.append(cand)
        else:
            rejected.append(RejectedCandidate(ticker=cand.ticker, reason=reason))
    trace.append(
        TraceStep(name="filtros", detail={"pasan": len(passed), "descartados": len(rejected)})
    )

    # 6) Puntuación y ranking
    scored = [score_candidate(c, criteria.weights, benchmarks.get(c.sector)) for c in passed]
    scored.sort(key=lambda s: s.score, reverse=True)
    ranked = scored[: criteria.max_results]
    trace.append(
        TraceStep(name="ranking", detail={"top": [{"ticker": s.ticker, "score": s.score} for s in ranked]})
    )

    # 7) Razonamiento + guardrail por finalista
    summary = _criteria_summary(criteria)
    justifications = [
        justify(sc, summary, client=client, model=reasoner_model, usage=usage) for sc in ranked
    ]
    guardrail_failures = [j.ticker for j in justifications if not j.guardrail_passed]
    if guardrail_failures:
        trace.append(TraceStep(name="guardrail_alertas", detail={"tickers": guardrail_failures}))

    return ScreenResult(
        criteria=criteria,
        ranked=ranked,
        justifications=justifications,
        rejected=rejected,
        trace=trace,
        token_usage=usage.as_dict(),
    )
