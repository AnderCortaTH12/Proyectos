"""Tests de gestión de riesgo: sizing 5%, anti-duplicado y topes."""
from trading_bot.broker.risk import decide_trade, position_notional
from trading_bot.models import BotConfig, TradeAction

from .fixtures.sample_data import make_account, make_position


def test_position_notional_respeta_5pct():
    acc = make_account(portfolio_value=100_000, buying_power=100_000)
    assert position_notional(acc, 0.05) == 5_000.0


def test_position_notional_limitado_por_buying_power():
    acc = make_account(portfolio_value=100_000, buying_power=2_000)
    # 5% serían 5000, pero solo hay 2000 de buying power.
    assert position_notional(acc, 0.05) == 2_000.0


def test_decide_compra_cuando_supera_umbral():
    acc = make_account()
    cfg = BotConfig(query="x", score_threshold=7.5, max_position_pct=0.05)
    d = decide_trade("AAPL", 8.2, "buena", acc, [], cfg)
    assert d.action == TradeAction.BUY
    assert d.target_notional == 5_000.0


def test_decide_skip_por_score_bajo():
    acc = make_account()
    cfg = BotConfig(query="x", score_threshold=7.5)
    d = decide_trade("AAPL", 6.0, "regular", acc, [], cfg)
    assert d.action == TradeAction.SKIP
    assert "umbral" in d.skip_reason


def test_decide_skip_por_duplicado():
    acc = make_account()
    cfg = BotConfig(query="x", score_threshold=7.5)
    d = decide_trade("MSFT", 9.0, "muy buena", acc, [make_position("MSFT")], cfg)
    assert d.action == TradeAction.SKIP
    assert "posición" in d.skip_reason


def test_decide_skip_por_max_posiciones():
    acc = make_account()
    cfg = BotConfig(query="x", score_threshold=7.5, max_open_positions=1)
    d = decide_trade("AAPL", 9.0, "ok", acc, [make_position("MSFT")], cfg)
    assert d.action == TradeAction.SKIP
    assert "máximo" in d.skip_reason


def test_decide_skip_sin_buying_power():
    acc = make_account(portfolio_value=100_000, buying_power=0)
    cfg = BotConfig(query="x", score_threshold=7.5)
    d = decide_trade("AAPL", 9.0, "ok", acc, [], cfg)
    assert d.action == TradeAction.SKIP
    assert "buying power" in d.skip_reason
