"""Esquemas Pydantic del broker (Alpaca) y del bot de trading."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Broker: órdenes ----------
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"


class OrderStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    PENDING = "pending"
    SIMULATED = "simulated"  # cuando trading_allowed es False (solo se loguea)


class OrderRequest(BaseModel):
    ticker: str
    side: OrderSide
    notional: Optional[float] = Field(None, gt=0)
    qty: Optional[float] = Field(None, gt=0)
    type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    limit_price: Optional[float] = Field(None, gt=0)
    client_order_id: str
    rationale: str = ""

    @model_validator(mode="after")
    def _check(self) -> "OrderRequest":
        if (self.notional is None) == (self.qty is None):
            raise ValueError("Indica exactamente uno: notional o qty")
        if self.type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Las órdenes LIMIT requieren limit_price")
        return self


class Order(BaseModel):
    id: str
    client_order_id: str
    ticker: str
    side: OrderSide
    qty: float
    status: OrderStatus
    filled_qty: float = 0.0
    filled_avg_price: Optional[float] = None
    submitted_at: datetime
    rationale: str = ""


# ---------- Broker: cuenta y posiciones ----------
class Account(BaseModel):
    cash: float
    equity: float
    buying_power: float
    portfolio_value: float
    currency: str = "USD"
    is_paper: bool = True


class Position(BaseModel):
    ticker: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float


# ---------- Bot: configuración y decisiones ----------
class BotConfig(BaseModel):
    query: str
    score_threshold: float = Field(7.5, ge=0, le=10)
    max_position_pct: float = Field(0.05, gt=0, le=0.20)
    interval_minutes: int = Field(60, ge=5)
    max_open_positions: int = Field(10, ge=1)
    paper: bool = True
    live_trading_enabled: bool = False
    is_active: bool = False


class TradeAction(str, Enum):
    BUY = "buy"
    SKIP = "skip"


class TradeDecision(BaseModel):
    ticker: str
    score: float
    action: TradeAction
    target_notional: Optional[float] = None
    sizing_reason: str = ""
    skip_reason: Optional[str] = None
    rationale: str = ""


class BotRunRecord(BaseModel):
    run_id: str
    timestamp: datetime
    query: str
    candidates_evaluated: int = 0
    decisions: list[TradeDecision] = Field(default_factory=list)
    orders_placed: list[Order] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    token_usage: dict[str, int | float] = Field(default_factory=dict)


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
