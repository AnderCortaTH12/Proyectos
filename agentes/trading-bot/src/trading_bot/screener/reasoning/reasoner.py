"""Reasoner: genera la justificación NL de cada finalista anclada a datos reales.

Pasa SIEMPRE las cifras reales al prompt y prohíbe inventar datos. El modelo debe
devolver, vía herramienta, el texto y la lista de números citados (con su
source_field), que después el guardrail verifica.
"""
import json
from typing import Optional

from ...telemetry import TokenUsage
from ..models import CitedNumber, Justification, ScoredCandidate
from .guardrail import available_numbers, verify

JUSTIFY_TOOL = {
    "name": "submit_justification",
    "description": "Entrega la justificación de por qué el valor encaja con los criterios.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Justificación en 2-4 frases, citando cifras concretas.",
            },
            "cited": {
                "type": "array",
                "description": "Cada número mencionado en el texto, con su campo de origen.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "number"},
                        "source_field": {
                            "type": "string",
                            "description": "Clave exacta del dato, ej. 'fundamentals.pe_ratio'.",
                        },
                    },
                    "required": ["label", "value", "source_field"],
                },
            },
        },
        "required": ["text", "cited"],
    },
}

SYSTEM = (
    "Eres un analista financiero. Justifica por qué una acción encaja con los "
    "criterios usando ÚNICAMENTE las cifras reales que se te proporcionan. Está "
    "TERMINANTEMENTE PROHIBIDO inventar o estimar números: cada cifra que cites debe "
    "existir en los datos y referenciar su source_field exacto. No es asesoramiento "
    "financiero. Llama a la herramienta submit_justification."
)


def _template_justification(sc: ScoredCandidate) -> Justification:
    """Justificación de respaldo (sin IA): describe las sub-puntuaciones reales."""
    c = sc.candidate
    cited = [
        CitedNumber(label="market cap", value=c.fundamentals.market_cap, source_field="fundamentals.market_cap"),
    ]
    if c.fundamentals.pe_ratio is not None:
        cited.append(CitedNumber(label="PER", value=c.fundamentals.pe_ratio, source_field="fundamentals.pe_ratio"))
    if c.technicals.rsi_14 is not None:
        cited.append(CitedNumber(label="RSI(14)", value=c.technicals.rsi_14, source_field="technicals.rsi_14"))
    text = (
        f"{c.ticker} ({c.sector}) obtiene una puntuación de {sc.score}/10 "
        f"(valoración {sc.sub_scores.get('valuation')}, momentum {sc.sub_scores.get('momentum')}, "
        f"calidad {sc.sub_scores.get('quality')})."
    )
    return verify(c, Justification(ticker=c.ticker, text=text, cited=cited))


def justify(
    sc: ScoredCandidate,
    criteria_summary: str,
    client=None,
    model: str = "claude-sonnet-4-6",
    usage: Optional[TokenUsage] = None,
) -> Justification:
    """Genera y verifica la justificación de un candidato finalista."""
    if client is None:
        return _template_justification(sc)
    try:
        data = {
            "ticker": sc.candidate.ticker,
            "sector": sc.candidate.sector,
            "score": sc.score,
            "sub_scores": sc.sub_scores,
            "datos_disponibles": available_numbers(sc.candidate),
        }
        prompt = (
            f"Criterios del usuario: {criteria_summary}\n\n"
            f"Datos reales del candidato (usa solo estos números):\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=[JUSTIFY_TOOL],
            tool_choice={"type": "tool", "name": "submit_justification"},
            messages=[{"role": "user", "content": prompt}],
        )
        if usage is not None and getattr(resp, "usage", None):
            usage.add(model, resp.usage.input_tokens, resp.usage.output_tokens)
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                args = block.input
                just = Justification(
                    ticker=sc.candidate.ticker,
                    text=args.get("text", ""),
                    cited=[CitedNumber(**c) for c in args.get("cited", [])],
                )
                return verify(sc.candidate, just)
        return _template_justification(sc)
    except Exception:
        return _template_justification(sc)
