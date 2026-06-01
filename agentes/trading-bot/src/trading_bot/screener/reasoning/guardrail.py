"""Guardrail: verifica que todo número citado en la justificación existe en los datos.

Construye un diccionario plano de los números reales del candidato
(fundamentals.* y technicals.*) y comprueba cada CitedNumber contra su
source_field con una tolerancia relativa. Si algo no cuadra, marca el problema.
"""
from ..models import Candidate, CitedNumber, Justification

_REL_TOL = 0.02  # 2% de tolerancia relativa (redondeos del modelo)


def available_numbers(cand: Candidate) -> dict[str, float]:
    """Aplana los números reales del candidato en claves tipo 'fundamentals.pe_ratio'."""
    flat: dict[str, float] = {}
    for prefix, snap in (("fundamentals", cand.fundamentals), ("technicals", cand.technicals)):
        for field_name, value in snap.model_dump().items():
            if isinstance(value, (int, float)):
                flat[f"{prefix}.{field_name}"] = float(value)
    # Propiedades calculadas de los técnicos.
    for prop in ("sma_50_200_cross", "price_vs_sma_200"):
        val = getattr(cand.technicals, prop, None)
        if isinstance(val, (int, float)):
            flat[f"technicals.{prop}"] = float(val)
    return flat


def _matches(cited: CitedNumber, available: dict[str, float]) -> tuple[bool, str]:
    if cited.source_field not in available:
        return False, f"'{cited.source_field}' no existe en los datos"
    real = available[cited.source_field]
    tol = max(abs(real) * _REL_TOL, 0.01)
    if abs(real - cited.value) > tol:
        return False, (
            f"'{cited.source_field}'={real:.4f} no coincide con el citado {cited.value:.4f}"
        )
    return True, ""


def verify(cand: Candidate, justification: Justification) -> Justification:
    """Devuelve la justificación anotada con guardrail_passed y los problemas hallados."""
    available = available_numbers(cand)
    issues: list[str] = []
    for cited in justification.cited:
        ok, reason = _matches(cited, available)
        if not ok:
            issues.append(reason)
    justification.guardrail_passed = len(issues) == 0
    justification.guardrail_issues = issues
    return justification
