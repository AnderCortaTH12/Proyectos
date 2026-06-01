"""TradingBot: une screener + risk + broker y registra cada decisión y orden."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..broker.alpaca_client import AlpacaBroker
from ..broker.risk import decide_trade
from ..logging_conf import get_logger, log_event
from ..models import (
    BotConfig,
    BotRunRecord,
    EquityPoint,
    OrderRequest,
    OrderSide,
    TradeAction,
    TradeDecision,
)
from ..screener.screen import run_screen
from ..screener.tools.cache import DataCache
from ..store.trade_log import TradeLog
from ..telemetry import TokenUsage


class TradingBot:
    """Ejecuta un ciclo completo: screening -> decisiones de riesgo -> órdenes -> log."""

    def __init__(
        self,
        config: BotConfig,
        broker: AlpacaBroker,
        cache: Optional[DataCache] = None,
        store: Optional[TradeLog] = None,
        anthropic_client=None,
        planner_model: str = "claude-haiku-4-5",
        reasoner_model: str = "claude-sonnet-4-6",
    ) -> None:
        self.config = config
        self.broker = broker
        self.cache = cache
        self.store = store
        self.anthropic_client = anthropic_client
        self.planner_model = planner_model
        self.reasoner_model = reasoner_model
        self.logger = get_logger("trading_bot")

    def run_once(self) -> BotRunRecord:
        """Ejecuta un ciclo de screening + trading y devuelve el registro de la ejecución."""
        run_id = uuid.uuid4().hex[:12]
        usage = TokenUsage()
        log_event(self.logger, "run_start", run_id=run_id, query=self.config.query)

        record = BotRunRecord(
            run_id=run_id, timestamp=datetime.now(timezone.utc), query=self.config.query
        )

        # 1) Screening
        try:
            result = run_screen(
                self.config.query,
                cache=self.cache,
                client=self.anthropic_client,
                planner_model=self.planner_model,
                reasoner_model=self.reasoner_model,
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001
            record.errors.append(f"screening: {exc}")
            log_event(self.logger, "run_error", run_id=run_id, error=str(exc))
            if self.store:
                self.store.record_run(record)
            return record

        record.candidates_evaluated = len(result.ranked)
        record.token_usage = result.token_usage

        # 2) Estado de la cuenta y posiciones
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        # Mapa de justificaciones por ticker (verificadas por el guardrail).
        justif = {j.ticker: j for j in result.justifications}

        # 3) Decisión + ejecución por candidato finalista
        for sc in result.ranked:
            j = justif.get(sc.ticker)
            rationale = j.text if j else ""
            decision: TradeDecision = decide_trade(
                ticker=sc.ticker,
                score=sc.score,
                rationale=rationale,
                account=account,
                positions=positions,
                config=self.config,
            )

            # No actuar sobre justificaciones que no pasen el guardrail.
            if decision.action == TradeAction.BUY and j and not j.guardrail_passed:
                decision.action = TradeAction.SKIP
                decision.skip_reason = "justificación no supera el guardrail (números no verificados)"

            record.decisions.append(decision)

            if decision.action == TradeAction.BUY and decision.target_notional:
                req = OrderRequest(
                    ticker=sc.ticker,
                    side=OrderSide.BUY,
                    notional=decision.target_notional,
                    client_order_id=f"{run_id}-{sc.ticker}",
                    rationale=decision.rationale,
                )
                try:
                    order = self.broker.place_order(req)
                    record.orders_placed.append(order)
                    positions = self.broker.get_positions()  # refrescar para anti-duplicado
                    log_event(
                        self.logger, "order_placed", run_id=run_id, ticker=sc.ticker,
                        notional=decision.target_notional, status=order.status.value,
                        rationale=decision.rationale,
                    )
                except Exception as exc:  # noqa: BLE001
                    record.errors.append(f"orden {sc.ticker}: {exc}")
                    log_event(self.logger, "order_error", run_id=run_id, ticker=sc.ticker, error=str(exc))
            else:
                log_event(
                    self.logger, "decision_skip", run_id=run_id, ticker=sc.ticker,
                    reason=decision.skip_reason or "",
                )

        # 4) Persistencia: run + punto de equity
        if self.store:
            self.store.record_run(record)
            self.store.add_equity_point(
                EquityPoint(timestamp=record.timestamp, equity=account.equity)
            )

        log_event(
            self.logger, "run_end", run_id=run_id,
            orders=len(record.orders_placed), cost_usd=record.token_usage.get("estimated_cost_usd"),
        )
        return record
