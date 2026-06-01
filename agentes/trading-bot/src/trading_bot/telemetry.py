"""Conteo de tokens y coste aproximado por ciclo del bot."""
from dataclasses import dataclass, field

# Precios aproximados (USD por millón de tokens). Ajustables; solo orientativos.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
}


@dataclass
class TokenUsage:
    """Acumulador de uso de tokens por modelo para estimar coste."""

    input_tokens: int = 0
    output_tokens: int = 0
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        m = self.by_model.setdefault(model, {"input": 0, "output": 0})
        m["input"] += input_tokens
        m["output"] += output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Coste estimado en USD según PRICES_PER_MTOK."""
        total = 0.0
        for model, counts in self.by_model.items():
            price = PRICES_PER_MTOK.get(model)
            if not price:
                continue
            total += counts["input"] / 1_000_000 * price["input"]
            total += counts["output"] / 1_000_000 * price["output"]
        return round(total, 4)

    def as_dict(self) -> dict[str, int | float]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }
