"""Tests del screener: filtros, scoring, planner heurístico y guardrail."""
from trading_bot.screener.engine.filters import passes_filters
from trading_bot.screener.engine.scoring import score_candidate
from trading_bot.screener.models import (
    Justification,
    CitedNumber,
    MomentumCondition,
    ScoreWeights,
    ScreenCriteria,
    SectorBenchmark,
    ValuationCondition,
)
from trading_bot.screener.parser.planner import _fallback_criteria
from trading_bot.screener.reasoning.guardrail import verify

from .fixtures.sample_data import make_candidate


def _benchmark():
    return SectorBenchmark(
        sector="Information Technology",
        medians={"pe_ratio": 25.0, "pb_ratio": 5.0, "price_to_sales": 6.0},
    )


def test_filtro_pasa_por_valoracion_relativa():
    cand = make_candidate(pe=15.0)  # < mediana 25
    crit = ScreenCriteria(
        raw_query="x",
        valuation=[ValuationCondition(metric="pe_ratio", comparator="<", reference="sector_median", value=1.0)],
    )
    ok, _ = passes_filters(cand, crit, _benchmark())
    assert ok is True


def test_filtro_descarta_por_valoracion():
    cand = make_candidate(pe=40.0)  # > mediana 25
    crit = ScreenCriteria(
        raw_query="x",
        valuation=[ValuationCondition(metric="pe_ratio", comparator="<", reference="sector_median", value=1.0)],
    )
    ok, reason = passes_filters(cand, crit, _benchmark())
    assert ok is False
    assert "pe_ratio" in reason


def test_filtro_descarta_por_momentum():
    cand = make_candidate(rsi=40.0)
    crit = ScreenCriteria(
        raw_query="x",
        momentum=[MomentumCondition(indicator="rsi_14", comparator=">", value=50.0)],
    )
    ok, reason = passes_filters(cand, crit, _benchmark())
    assert ok is False
    assert "rsi_14" in reason


def test_score_en_rango_0_10():
    cand = make_candidate()
    sc = score_candidate(cand, ScoreWeights(), _benchmark())
    assert 0.0 <= sc.score <= 10.0
    assert set(sc.sub_scores) == {"valuation", "momentum", "quality"}


def test_accion_barata_puntua_mas_que_cara():
    barata = make_candidate(ticker="CHEAP", pe=10.0)
    cara = make_candidate(ticker="EXP", pe=40.0)
    w = ScoreWeights(valuation=1.0, momentum=0.0, quality=0.0)
    assert score_candidate(barata, w, _benchmark()).score > score_candidate(cara, w, _benchmark()).score


def test_planner_fallback_detecta_tech_y_momentum():
    crit = _fallback_criteria("tech infravalorada con momentum positivo")
    assert "Information Technology" in crit.sectors
    assert any(v.metric == "pe_ratio" for v in crit.valuation)
    assert any(m.indicator in {"rsi_14", "return_3m"} for m in crit.momentum)


def test_guardrail_acepta_numeros_reales():
    cand = make_candidate(pe=15.0)
    just = Justification(
        ticker=cand.ticker, text="PER 15",
        cited=[CitedNumber(label="PER", value=15.0, source_field="fundamentals.pe_ratio")],
    )
    verify(cand, just)
    assert just.guardrail_passed is True


def test_guardrail_detecta_numero_inventado():
    cand = make_candidate(pe=15.0)
    just = Justification(
        ticker=cand.ticker, text="PER 8",
        cited=[CitedNumber(label="PER", value=8.0, source_field="fundamentals.pe_ratio")],
    )
    verify(cand, just)
    assert just.guardrail_passed is False
    assert just.guardrail_issues
