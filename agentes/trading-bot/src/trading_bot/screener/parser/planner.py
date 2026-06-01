"""Planner: consulta NL -> ScreenCriteria, usando Haiku con tool use.

Si no hay cliente/clave de Anthropic disponible, cae a un parser heurístico por
palabras clave para que la demo siga funcionando offline (y para los tests).
"""
from typing import Optional

from ...telemetry import TokenUsage
from ..models import (
    MarketCapBand,
    MarketCapRange,
    MomentumCondition,
    ScreenCriteria,
    ValuationCondition,
)

# Esquema de la herramienta que el modelo debe rellenar.
CRITERIA_TOOL = {
    "name": "set_screen_criteria",
    "description": "Define los criterios estructurados de screening a partir de la consulta.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sectors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sectores GICS (ej. 'Information Technology'). Vacío = todos.",
            },
            "market_cap_band": {
                "type": "string",
                "enum": ["micro", "small", "mid", "large", "mega"],
                "description": "Banda de capitalización si la consulta la sugiere.",
            },
            "valuation": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "enum": ["pe_ratio", "forward_pe", "pb_ratio", "ev_ebitda",
                                     "price_to_sales", "dividend_yield", "peg_ratio"],
                        },
                        "comparator": {"type": "string", "enum": ["<", "<=", ">", ">="]},
                        "reference": {"type": "string", "enum": ["sector_median", "absolute"]},
                        "value": {"type": "number"},
                    },
                    "required": ["metric", "comparator", "value"],
                },
            },
            "momentum": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "indicator": {
                            "type": "string",
                            "enum": ["rsi_14", "macd_hist", "sma_50_200_cross",
                                     "price_vs_sma_200", "return_1m", "return_3m", "return_6m"],
                        },
                        "comparator": {"type": "string", "enum": ["<", "<=", ">", ">="]},
                        "value": {"type": "number"},
                    },
                    "required": ["indicator", "comparator", "value"],
                },
            },
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
            "interpretation_notes": {"type": "string"},
        },
        "required": [],
    },
}

SYSTEM = (
    "Eres un analista que traduce consultas de inversión en lenguaje natural a "
    "criterios estructurados de screening. Usa umbrales relativos a la mediana del "
    "sector cuando la consulta hable de 'infravalorada', 'barata' respecto al sector. "
    "Para 'momentum positivo' usa indicadores como rsi_14>50, return_3m>0 o cruce de "
    "medias. Llama SIEMPRE a la herramienta set_screen_criteria. No inventes tickers."
)


def _args_to_criteria(query: str, args: dict) -> ScreenCriteria:
    market_cap = None
    if args.get("market_cap_band"):
        market_cap = MarketCapRange(band=MarketCapBand(args["market_cap_band"]))
    return ScreenCriteria(
        raw_query=query,
        sectors=args.get("sectors", []) or [],
        market_cap=market_cap,
        valuation=[ValuationCondition(**v) for v in args.get("valuation", [])],
        momentum=[MomentumCondition(**m) for m in args.get("momentum", [])],
        max_results=args.get("max_results", 10),
        interpretation_notes=args.get("interpretation_notes"),
    )


def _fallback_criteria(query: str) -> ScreenCriteria:
    """Parser heurístico por palabras clave (sin IA)."""
    q = query.lower()
    sectors: list[str] = []
    if "tech" in q or "tecnolog" in q:
        sectors.append("Information Technology")
    if "salud" in q or "health" in q:
        sectors.append("Health Care")
    if "financ" in q or "banco" in q:
        sectors.append("Financials")

    band = None
    if "mega" in q:
        band = MarketCapBand.MEGA
    elif "gran" in q or "large" in q:
        band = MarketCapBand.LARGE
    elif "mediana" in q or "mid" in q:
        band = MarketCapBand.MID
    elif "pequeñ" in q or "small" in q:
        band = MarketCapBand.SMALL

    valuation = []
    if "infravalor" in q or "barat" in q or "undervalu" in q:
        valuation.append(
            ValuationCondition(metric="pe_ratio", comparator="<", reference="sector_median", value=1.0)
        )
    momentum = []
    if "momentum" in q or "alcista" in q:
        momentum.append(MomentumCondition(indicator="return_3m", comparator=">", value=0.0))
        momentum.append(MomentumCondition(indicator="rsi_14", comparator=">", value=50.0))

    return ScreenCriteria(
        raw_query=query,
        sectors=sectors,
        market_cap=MarketCapRange(band=band) if band else None,
        valuation=valuation,
        momentum=momentum,
        interpretation_notes="Criterios derivados por heurística (sin IA).",
    )


def plan(
    query: str,
    client=None,
    model: str = "claude-haiku-4-5",
    usage: Optional[TokenUsage] = None,
) -> ScreenCriteria:
    """Convierte la consulta NL en ScreenCriteria. Cae a heurística ante cualquier fallo."""
    if client is None:
        return _fallback_criteria(query)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=[CRITERIA_TOOL],
            tool_choice={"type": "tool", "name": "set_screen_criteria"},
            messages=[{"role": "user", "content": query}],
        )
        if usage is not None and getattr(resp, "usage", None):
            usage.add(model, resp.usage.input_tokens, resp.usage.output_tokens)
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return _args_to_criteria(query, block.input)
        return _fallback_criteria(query)
    except Exception:
        return _fallback_criteria(query)
