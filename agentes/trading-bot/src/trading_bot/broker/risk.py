"""Gestión de riesgo: tamaño de posición (máx 5%) y prevención de duplicados.

Funciones puras (sin red) para que sean fáciles de testear.
"""
from ..models import Account, BotConfig, Position, TradeAction, TradeDecision


def position_notional(account: Account, max_position_pct: float) -> float:
    """Importe objetivo por posición: % del portfolio, limitado por el buying power."""
    target = account.portfolio_value * max_position_pct
    return round(max(0.0, min(target, account.buying_power)), 2)


def decide_trade(
    ticker: str,
    score: float,
    rationale: str,
    account: Account,
    positions: list[Position],
    config: BotConfig,
) -> TradeDecision:
    """Decide si comprar un candidato aplicando todas las reglas de riesgo."""
    held = {p.ticker for p in positions}

    # 1) Umbral de score
    if score < config.score_threshold:
        return TradeDecision(
            ticker=ticker, score=score, action=TradeAction.SKIP,
            skip_reason=f"score {score} < umbral {config.score_threshold}", rationale=rationale,
        )

    # 2) Anti-duplicado: ya tenemos posición
    if ticker in held:
        return TradeDecision(
            ticker=ticker, score=score, action=TradeAction.SKIP,
            skip_reason="ya existe posición abierta en el ticker", rationale=rationale,
        )

    # 3) Tope de posiciones abiertas
    if len(positions) >= config.max_open_positions:
        return TradeDecision(
            ticker=ticker, score=score, action=TradeAction.SKIP,
            skip_reason=f"alcanzado el máximo de {config.max_open_positions} posiciones",
            rationale=rationale,
        )

    # 4) Sizing
    notional = position_notional(account, config.max_position_pct)
    if notional <= 1.0:
        return TradeDecision(
            ticker=ticker, score=score, action=TradeAction.SKIP,
            skip_reason="sin buying power suficiente", rationale=rationale,
        )

    pct = (notional / account.portfolio_value * 100) if account.portfolio_value else 0
    return TradeDecision(
        ticker=ticker,
        score=score,
        action=TradeAction.BUY,
        target_notional=notional,
        sizing_reason=f"{config.max_position_pct*100:.1f}% de ${account.portfolio_value:,.0f} = ${notional:,.0f} ({pct:.1f}%)",
        rationale=rationale,
    )
