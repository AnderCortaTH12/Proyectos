"""Esquemas Pydantic del screener: criterios, datos de mercado y resultados."""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Vocabulario controlado ----------
class Comparator(str, Enum):
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="

    def compare(self, a: float, b: float) -> bool:
        return {
            Comparator.LT: a < b,
            Comparator.LTE: a <= b,
            Comparator.GT: a > b,
            Comparator.GTE: a >= b,
        }[self]


class MarketCapBand(str, Enum):
    MICRO = "micro"   # < 300M
    SMALL = "small"   # 300M – 2B
    MID = "mid"       # 2B – 10B
    LARGE = "large"   # 10B – 200B
    MEGA = "mega"     # > 200B

    def to_range(self) -> tuple[Optional[float], Optional[float]]:
        return {
            MarketCapBand.MICRO: (None, 300e6),
            MarketCapBand.SMALL: (300e6, 2e9),
            MarketCapBand.MID: (2e9, 10e9),
            MarketCapBand.LARGE: (10e9, 200e9),
            MarketCapBand.MEGA: (200e9, None),
        }[self]


ValuationMetric = Literal[
    "pe_ratio", "forward_pe", "pb_ratio", "ev_ebitda",
    "price_to_sales", "dividend_yield", "peg_ratio",
]
MomentumIndicator = Literal[
    "rsi_14", "macd_hist", "sma_50_200_cross", "price_vs_sma_200",
    "return_1m", "return_3m", "return_6m",
]
Reference = Literal["sector_median", "absolute"]


# ---------- Sub-objetos de criterio ----------
class MarketCapRange(BaseModel):
    min_usd: Optional[float] = Field(None, ge=0)
    max_usd: Optional[float] = Field(None, ge=0)
    band: Optional[MarketCapBand] = None

    @model_validator(mode="after")
    def _resolve(self) -> "MarketCapRange":
        # Si se da una banda y no rangos explícitos, derivarlos.
        if self.band and self.min_usd is None and self.max_usd is None:
            self.min_usd, self.max_usd = self.band.to_range()
        if self.min_usd is not None and self.max_usd is not None and self.min_usd > self.max_usd:
            raise ValueError("min_usd no puede ser mayor que max_usd")
        return self

    def contains(self, market_cap: float) -> bool:
        if self.min_usd is not None and market_cap < self.min_usd:
            return False
        if self.max_usd is not None and market_cap > self.max_usd:
            return False
        return True


class ValuationCondition(BaseModel):
    """Ej.: PER por debajo del 80% de la mediana del sector."""

    metric: ValuationMetric
    comparator: Comparator
    reference: Reference = "sector_median"
    value: float  # multiplicador (si sector_median) o umbral absoluto


class MomentumCondition(BaseModel):
    """Ej.: RSI(14) > 50, o cruce dorado SMA50/200 activo (value=1)."""

    indicator: MomentumIndicator
    comparator: Comparator
    value: float


class ScoreWeights(BaseModel):
    valuation: float = 0.4
    momentum: float = 0.4
    quality: float = 0.2

    @model_validator(mode="after")
    def _normalize(self) -> "ScoreWeights":
        total = self.valuation + self.momentum + self.quality
        if total <= 0:
            raise ValueError("Los pesos deben sumar > 0")
        self.valuation /= total
        self.momentum /= total
        self.quality /= total
        return self


class ScreenCriteria(BaseModel):
    """Criterios estructurados producidos por el planner a partir de la consulta NL."""

    raw_query: str
    universe: Literal["sp500"] = "sp500"
    sectors: list[str] = Field(default_factory=list)
    market_cap: Optional[MarketCapRange] = None
    valuation: list[ValuationCondition] = Field(default_factory=list)
    momentum: list[MomentumCondition] = Field(default_factory=list)
    max_results: int = Field(10, ge=1, le=50)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    interpretation_notes: Optional[str] = None


# ---------- Datos de mercado ----------
class FundamentalSnapshot(BaseModel):
    ticker: str
    name: str = ""
    sector: str = ""
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    dividend_yield: Optional[float] = None
    peg_ratio: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    profit_margin: Optional[float] = None


class TechnicalSnapshot(BaseModel):
    ticker: str
    price: float = 0.0
    rsi_14: Optional[float] = None
    macd_hist: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None

    @property
    def sma_50_200_cross(self) -> Optional[float]:
        """1.0 si cruce dorado (SMA50>SMA200), 0.0 si muerte, None si faltan datos."""
        if self.sma_50 is None or self.sma_200 is None:
            return None
        return 1.0 if self.sma_50 > self.sma_200 else 0.0

    @property
    def price_vs_sma_200(self) -> Optional[float]:
        """1.0 si el precio está por encima de la SMA200, 0.0 si por debajo."""
        if self.sma_200 is None or self.price == 0:
            return None
        return 1.0 if self.price > self.sma_200 else 0.0


class SectorBenchmark(BaseModel):
    """Medianas de métricas de valoración por sector (para umbrales relativos)."""

    sector: str
    medians: dict[str, float] = Field(default_factory=dict)


# ---------- Candidatos y resultados ----------
class CitedNumber(BaseModel):
    """Número citado por el reasoning; el guardrail verifica que exista en origen."""

    label: str
    value: float
    source_field: str  # p.ej. "fundamentals.pe_ratio"


class Candidate(BaseModel):
    ticker: str
    name: str = ""
    sector: str = ""
    fundamentals: FundamentalSnapshot
    technicals: TechnicalSnapshot


class ScoredCandidate(BaseModel):
    candidate: Candidate
    score: float  # 0–10
    sub_scores: dict[str, float] = Field(default_factory=dict)

    @property
    def ticker(self) -> str:
        return self.candidate.ticker


class RejectedCandidate(BaseModel):
    ticker: str
    reason: str


class Justification(BaseModel):
    ticker: str
    text: str
    cited: list[CitedNumber] = Field(default_factory=list)
    guardrail_passed: bool = True
    guardrail_issues: list[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    name: str
    detail: dict = Field(default_factory=dict)


class ScreenResult(BaseModel):
    criteria: ScreenCriteria
    ranked: list[ScoredCandidate] = Field(default_factory=list)
    justifications: list[Justification] = Field(default_factory=list)
    rejected: list[RejectedCandidate] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    token_usage: dict[str, int | float] = Field(default_factory=dict)
