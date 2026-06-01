"""Tests del wrapper de Alpaca: modo simulado y lecturas con cliente mock."""
from trading_bot.broker.alpaca_client import AlpacaBroker
from trading_bot.models import OrderRequest, OrderSide, OrderStatus

from .fixtures.sample_data import MockTradingClient


def test_place_order_simulado_si_trading_no_permitido():
    broker = AlpacaBroker(trading_allowed=False, client=None)
    req = OrderRequest(
        ticker="AAPL", side=OrderSide.BUY, notional=1000, client_order_id="run-AAPL"
    )
    order = broker.place_order(req)
    assert order.status == OrderStatus.SIMULATED
    assert order.id == "SIMULATED"
    assert order.ticker == "AAPL"


def test_get_account_mapea_cliente_mock():
    broker = AlpacaBroker(trading_allowed=True, client=MockTradingClient(), paper=True)
    acc = broker.get_account()
    assert acc.equity == 100_000.0
    assert acc.buying_power == 100_000.0
    assert acc.is_paper is True


def test_get_positions_vacio():
    broker = AlpacaBroker(trading_allowed=True, client=MockTradingClient())
    assert broker.get_positions() == []
