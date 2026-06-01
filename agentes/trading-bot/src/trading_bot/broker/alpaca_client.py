"""Wrapper del SDK de Alpaca (alpaca-py) mapeado a nuestros modelos Pydantic.

Si el trading no está permitido (paper desactivado sin ENABLE_LIVE_TRADING, o sin
cliente), place_order NO llama a la API: devuelve una orden con estado SIMULATED
para que el bot pueda loguear la decisión sin ejecutar nada.
"""
from datetime import datetime, timezone
from typing import Optional

from ..models import Account, Order, OrderRequest, OrderSide, OrderStatus, OrderType, Position
from .broker_interface import BrokerInterface


class AlpacaBroker(BrokerInterface):
    """Cliente de trading sobre Alpaca; admite inyección de cliente para tests."""

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        paper: bool = True,
        trading_allowed: bool = True,
        client=None,
    ) -> None:
        self.paper = paper
        self.trading_allowed = trading_allowed
        self._client = client
        if self._client is None and api_key and secret_key:
            self._client = self._build_client(api_key, secret_key, paper)

    @staticmethod
    def _build_client(api_key: str, secret_key: str, paper: bool):
        from alpaca.trading.client import TradingClient

        return TradingClient(api_key, secret_key, paper=paper)

    @property
    def connected(self) -> bool:
        return self._client is not None

    # ---------- Lecturas ----------
    def get_account(self) -> Account:
        if not self._client:
            return Account(cash=0, equity=0, buying_power=0, portfolio_value=0, is_paper=self.paper)
        a = self._client.get_account()
        return Account(
            cash=float(a.cash),
            equity=float(a.equity),
            buying_power=float(a.buying_power),
            portfolio_value=float(a.portfolio_value),
            currency=getattr(a, "currency", "USD"),
            is_paper=self.paper,
        )

    def get_positions(self) -> list[Position]:
        if not self._client:
            return []
        out: list[Position] = []
        for p in self._client.get_all_positions():
            out.append(
                Position(
                    ticker=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    market_value=float(p.market_value),
                    cost_basis=float(p.cost_basis),
                    unrealized_pl=float(p.unrealized_pl),
                    unrealized_plpc=float(p.unrealized_plpc),
                )
            )
        return out

    def get_orders(self) -> list[Order]:
        if not self._client:
            return []
        from alpaca.trading.requests import GetOrdersRequest

        raw = self._client.get_orders(filter=GetOrdersRequest(limit=100))
        return [self._map_order(o) for o in raw]

    # ---------- Escritura ----------
    def place_order(self, req: OrderRequest) -> Order:
        """Envía una orden a Alpaca, o la simula si el trading no está permitido."""
        if not self.trading_allowed or not self._client:
            return Order(
                id="SIMULATED",
                client_order_id=req.client_order_id,
                ticker=req.ticker,
                side=req.side,
                qty=req.qty or 0.0,
                status=OrderStatus.SIMULATED,
                submitted_at=datetime.now(timezone.utc),
                rationale=req.rationale,
            )

        from alpaca.trading.enums import OrderSide as AlpacaSide
        from alpaca.trading.enums import TimeInForce as AlpacaTIF
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        side = AlpacaSide.BUY if req.side == OrderSide.BUY else AlpacaSide.SELL
        tif = AlpacaTIF.DAY if req.time_in_force.value == "day" else AlpacaTIF.GTC
        common = dict(
            symbol=req.ticker,
            side=side,
            time_in_force=tif,
            client_order_id=req.client_order_id,
        )
        if req.qty is not None:
            common["qty"] = req.qty
        else:
            common["notional"] = req.notional

        if req.type == OrderType.LIMIT:
            order_data = LimitOrderRequest(limit_price=req.limit_price, **common)
        else:
            order_data = MarketOrderRequest(**common)

        submitted = self._client.submit_order(order_data=order_data)
        order = self._map_order(submitted)
        order.rationale = req.rationale
        return order

    # ---------- Mapeo ----------
    @staticmethod
    def _map_order(o) -> Order:
        return Order(
            id=str(o.id),
            client_order_id=str(getattr(o, "client_order_id", "")),
            ticker=o.symbol,
            side=OrderSide(o.side.value if hasattr(o.side, "value") else str(o.side)),
            qty=float(o.qty) if o.qty is not None else 0.0,
            status=AlpacaBroker._map_status(str(o.status)),
            filled_qty=float(getattr(o, "filled_qty", 0) or 0),
            filled_avg_price=(
                float(o.filled_avg_price) if getattr(o, "filled_avg_price", None) else None
            ),
            submitted_at=getattr(o, "submitted_at", None) or datetime.now(timezone.utc),
        )

    @staticmethod
    def _map_status(raw: str) -> OrderStatus:
        raw = raw.lower().split(".")[-1]
        try:
            return OrderStatus(raw)
        except ValueError:
            mapping = {
                "filled": OrderStatus.FILLED,
                "partially_filled": OrderStatus.PARTIALLY_FILLED,
                "new": OrderStatus.NEW,
                "accepted": OrderStatus.ACCEPTED,
                "pending_new": OrderStatus.PENDING,
                "canceled": OrderStatus.CANCELED,
                "rejected": OrderStatus.REJECTED,
            }
            return mapping.get(raw, OrderStatus.PENDING)
