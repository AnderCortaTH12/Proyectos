"""Test del ciclo completo del bot con screening mockeado y broker simulado."""
import trading_bot.bot.trading_bot as bot_module
from trading_bot.bot.trading_bot import TradingBot
from trading_bot.broker.alpaca_client import AlpacaBroker
from trading_bot.models import BotConfig, OrderStatus, TradeAction
from trading_bot.screener.models import (
    Justification,
    ScoredCandidate,
    ScreenCriteria,
    ScreenResult,
)

from .fixtures.sample_data import MockTradingClient, make_candidate


def _fake_result(ticker: str, score: float, guardrail_ok: bool = True) -> ScreenResult:
    cand = make_candidate(ticker=ticker)
    sc = ScoredCandidate(candidate=cand, score=score, sub_scores={"valuation": 8, "momentum": 8, "quality": 7})
    just = Justification(ticker=ticker, text="ok", guardrail_passed=guardrail_ok)
    return ScreenResult(criteria=ScreenCriteria(raw_query="x"), ranked=[sc], justifications=[just])


def _make_bot(config: BotConfig) -> TradingBot:
    broker = AlpacaBroker(trading_allowed=False, client=MockTradingClient(), paper=True)
    return TradingBot(config=config, broker=broker, cache=None, store=None, anthropic_client=None)


def test_run_once_compra_y_simula_orden(monkeypatch):
    monkeypatch.setattr(bot_module, "run_screen", lambda *a, **k: _fake_result("AAPL", 9.0))
    bot = _make_bot(BotConfig(query="tech", score_threshold=7.5))
    record = bot.run_once()

    assert len(record.decisions) == 1
    assert record.decisions[0].action == TradeAction.BUY
    assert len(record.orders_placed) == 1
    assert record.orders_placed[0].status == OrderStatus.SIMULATED


def test_run_once_skip_si_guardrail_falla(monkeypatch):
    monkeypatch.setattr(
        bot_module, "run_screen", lambda *a, **k: _fake_result("AAPL", 9.0, guardrail_ok=False)
    )
    bot = _make_bot(BotConfig(query="tech", score_threshold=7.5))
    record = bot.run_once()

    assert record.decisions[0].action == TradeAction.SKIP
    assert "guardrail" in record.decisions[0].skip_reason
    assert len(record.orders_placed) == 0


def test_run_once_skip_por_score_bajo(monkeypatch):
    monkeypatch.setattr(bot_module, "run_screen", lambda *a, **k: _fake_result("AAPL", 5.0))
    bot = _make_bot(BotConfig(query="tech", score_threshold=7.5))
    record = bot.run_once()

    assert record.decisions[0].action == TradeAction.SKIP
    assert len(record.orders_placed) == 0
