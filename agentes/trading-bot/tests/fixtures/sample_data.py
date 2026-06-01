"""Datos de ejemplo para tests (sin red)."""
from datetime import datetime, timezone

from trading_bot.models import Account, Position
from trading_bot.screener.models import (
    Candidate,
    FundamentalSnapshot,
    TechnicalSnapshot,
)


def make_candidate(
    ticker: str = "AAPL",
    sector: str = "Information Technology",
    market_cap: float = 5e9,
    pe: float = 15.0,
    rsi: float = 60.0,
    sma50: float = 110.0,
    sma200: float = 100.0,
    price: float = 120.0,
    ret3m: float = 8.0,
    roe: float = 0.25,
) -> Candidate:
    return Candidate(
        ticker=ticker,
        name=ticker,
        sector=sector,
        fundamentals=FundamentalSnapshot(
            ticker=ticker, name=ticker, sector=sector, market_cap=market_cap,
            pe_ratio=pe, pb_ratio=3.0, price_to_sales=4.0, roe=roe,
            profit_margin=0.2, debt_to_equity=50.0,
        ),
        technicals=TechnicalSnapshot(
            ticker=ticker, price=price, rsi_14=rsi, macd_hist=0.5,
            sma_50=sma50, sma_200=sma200, return_1m=3.0, return_3m=ret3m, return_6m=12.0,
        ),
    )


def make_account(portfolio_value: float = 100_000.0, buying_power: float = 100_000.0) -> Account:
    return Account(
        cash=buying_power, equity=portfolio_value, buying_power=buying_power,
        portfolio_value=portfolio_value, is_paper=True,
    )


def make_position(ticker: str = "MSFT") -> Position:
    return Position(
        ticker=ticker, qty=10, avg_entry_price=100, current_price=110,
        market_value=1100, cost_basis=1000, unrealized_pl=100, unrealized_plpc=0.1,
    )


class FakeAlpacaAccount:
    cash = "50000"; equity = "100000"; buying_power = "100000"
    portfolio_value = "100000"; currency = "USD"


class MockTradingClient:
    """Cliente Alpaca mínimo para tests de lectura (sin importar alpaca-py)."""

    def get_account(self):
        return FakeAlpacaAccount()

    def get_all_positions(self):
        return []

    def get_orders(self, filter=None):  # noqa: A002
        return []


def now() -> datetime:
    return datetime.now(timezone.utc)
