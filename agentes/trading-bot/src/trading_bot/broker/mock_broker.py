"""MockBroker: broker SIMULADO 100% local.

================================================================================
ESTE BROKER NO SE CONECTA A NINGÚN BROKER REAL NI USA CREDENCIALES.
No mueve dinero real. Simula una cartera en memoria con un balance inicial
ficticio para poder probar el bot de extremo a extremo sin API keys ni riesgo.
================================================================================
"""
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from ..models import Account, Order, OrderRequest, OrderSide, OrderStatus, Position
from .broker_interface import BrokerInterface


def _default_price_provider(symbol: str) -> float:
    """Precio actual vía yfinance; 0.0 si no hay datos/red (no rompe la demo)."""
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="1d", auto_adjust=True)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0


class _Holding:
    """Posición interna del MockBroker (cantidad y precio medio de entrada)."""

    def __init__(self, qty: float, avg_price: float) -> None:
        self.qty = qty
        self.avg_price = avg_price


class MockBroker(BrokerInterface):
    """Cartera simulada en memoria. Implementa BrokerInterface sin red real."""

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        price_provider: Optional[Callable[[str], float]] = None,
    ) -> None:
        self.trading_allowed = True
        self.cash = starting_cash
        self._holdings: dict[str, _Holding] = {}
        self._orders: list[Order] = []
        self._price = price_provider or _default_price_provider

    # ---------- Lecturas ----------
    def get_account(self) -> Account:
        positions_value = sum(h.qty * self._price(sym) for sym, h in self._holdings.items())
        portfolio_value = self.cash + positions_value
        return Account(
            cash=round(self.cash, 2),
            equity=round(portfolio_value, 2),
            buying_power=round(self.cash, 2),
            portfolio_value=round(portfolio_value, 2),
            currency="USD",
            is_paper=True,
        )

    def get_positions(self) -> list[Position]:
        out: list[Position] = []
        for sym, h in self._holdings.items():
            if h.qty == 0:
                continue
            price = self._price(sym)
            market_value = h.qty * price
            cost_basis = h.qty * h.avg_price
            pl = market_value - cost_basis
            out.append(
                Position(
                    ticker=sym,
                    qty=round(h.qty, 4),
                    avg_entry_price=round(h.avg_price, 2),
                    current_price=round(price, 2),
                    market_value=round(market_value, 2),
                    cost_basis=round(cost_basis, 2),
                    unrealized_pl=round(pl, 2),
                    unrealized_plpc=round(pl / cost_basis, 4) if cost_basis else 0.0,
                )
            )
        return out

    def get_orders(self) -> list[Order]:
        return list(reversed(self._orders))

    # ---------- Escritura (simulada) ----------
    def place_order(self, req: OrderRequest) -> Order:
        """Simula la ejecución de una orden a precio de mercado actual."""
        price = self._price(req.ticker)
        order = Order(
            id=uuid.uuid4().hex[:12],
            client_order_id=req.client_order_id,
            ticker=req.ticker,
            side=req.side,
            qty=0.0,
            status=OrderStatus.REJECTED,
            submitted_at=datetime.now(timezone.utc),
            rationale=req.rationale,
        )

        if price <= 0:
            order.rationale = (req.rationale + " | rechazada: sin precio").strip(" |")
            self._orders.append(order)
            return order

        qty = req.qty if req.qty is not None else (req.notional or 0.0) / price

        if req.side == OrderSide.BUY:
            cost = qty * price
            if cost > self.cash:
                order.rationale = (req.rationale + " | rechazada: fondos insuficientes").strip(" |")
                self._orders.append(order)
                return order
            self.cash -= cost
            self._apply_buy(req.ticker, qty, price)
        else:  # SELL
            held = self._holdings.get(req.ticker)
            if not held or held.qty < qty:
                order.rationale = (req.rationale + " | rechazada: sin posición suficiente").strip(" |")
                self._orders.append(order)
                return order
            self.cash += qty * price
            held.qty -= qty

        order.qty = round(qty, 4)
        order.status = OrderStatus.FILLED
        order.filled_qty = round(qty, 4)
        order.filled_avg_price = round(price, 2)
        self._orders.append(order)
        return order

    def _apply_buy(self, symbol: str, qty: float, price: float) -> None:
        """Actualiza la posición con precio medio ponderado."""
        held = self._holdings.get(symbol)
        if held is None:
            self._holdings[symbol] = _Holding(qty=qty, avg_price=price)
        else:
            total_cost = held.qty * held.avg_price + qty * price
            held.qty += qty
            held.avg_price = total_cost / held.qty if held.qty else price
