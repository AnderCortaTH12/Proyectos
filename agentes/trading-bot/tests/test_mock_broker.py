"""Tests del MockBroker: cartera simulada, fills, P&L y validaciones (sin red)."""
from trading_bot.broker.mock_broker import MockBroker
from trading_bot.models import OrderRequest, OrderSide, OrderStatus


def _broker(prices: dict[str, float], cash: float = 100_000.0) -> MockBroker:
    return MockBroker(starting_cash=cash, price_provider=lambda s: prices.get(s, 0.0))


def test_balance_inicial():
    b = _broker({})
    acc = b.get_account()
    assert acc.cash == 100_000.0
    assert acc.portfolio_value == 100_000.0


def test_compra_resta_cash_y_crea_posicion():
    b = _broker({"AAPL": 100.0})
    order = b.place_order(
        OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=5_000, client_order_id="o1")
    )
    assert order.status == OrderStatus.FILLED
    assert order.qty == 50.0
    assert b.get_account().cash == 95_000.0
    positions = b.get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "AAPL"
    assert positions[0].qty == 50.0


def test_pnl_en_tiempo_real():
    prices = {"AAPL": 100.0}
    b = _broker(prices)
    b.place_order(OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=5_000, client_order_id="o1"))
    prices["AAPL"] = 110.0  # el precio sube
    pos = b.get_positions()[0]
    assert pos.unrealized_pl == 500.0  # 50 acciones * (110 - 100)
    # equity = cash 95k + 50*110 = 100.5k
    assert b.get_account().equity == 100_500.0


def test_rechaza_si_fondos_insuficientes():
    b = _broker({"AAPL": 100.0}, cash=1_000.0)
    order = b.place_order(
        OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=5_000, client_order_id="o1")
    )
    assert order.status == OrderStatus.REJECTED
    assert b.get_account().cash == 1_000.0
    assert b.get_positions() == []


def test_rechaza_si_sin_precio():
    b = _broker({})  # sin precio para AAPL -> 0.0
    order = b.place_order(
        OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=5_000, client_order_id="o1")
    )
    assert order.status == OrderStatus.REJECTED


def test_venta_reduce_posicion_y_devuelve_cash():
    prices = {"AAPL": 100.0}
    b = _broker(prices)
    b.place_order(OrderRequest(ticker="AAPL", side=OrderSide.BUY, qty=50, client_order_id="o1"))
    sell = b.place_order(OrderRequest(ticker="AAPL", side=OrderSide.SELL, qty=20, client_order_id="o2"))
    assert sell.status == OrderStatus.FILLED
    assert b.get_positions()[0].qty == 30.0


def test_historico_de_ordenes():
    b = _broker({"AAPL": 100.0})
    b.place_order(OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=1_000, client_order_id="o1"))
    b.place_order(OrderRequest(ticker="AAPL", side=OrderSide.BUY, notional=1_000, client_order_id="o2"))
    orders = b.get_orders()
    assert len(orders) == 2
    assert orders[0].client_order_id == "o2"  # más reciente primero
