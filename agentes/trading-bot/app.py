"""UI Streamlit del bot de trading: control, posiciones, órdenes, equity y logs.

DEMOSTRATIVO — NO es asesoramiento financiero. Paper trading por defecto.
"""
import os
import sys

# Permite importar el paquete desde src/ al ejecutar `streamlit run app.py`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from config import get_alpaca_settings, get_settings  # noqa: E402
from trading_bot.bot import BotScheduler, TradingBot  # noqa: E402
from trading_bot.broker.alpaca_client import AlpacaBroker  # noqa: E402
from trading_bot.models import BotConfig  # noqa: E402
from trading_bot.screener.tools.cache import DataCache  # noqa: E402
from trading_bot.store import TradeLog  # noqa: E402

st.set_page_config(page_title="Trading Bot Agéntico", page_icon="📈", layout="wide")

settings = get_settings()
alpaca = get_alpaca_settings()


# ---------- Construcción de componentes (cacheados en sesión) ----------
@st.cache_resource
def get_components():
    cache = DataCache(settings.cache_db_path, settings.cache_ttl_hours)
    store = TradeLog(settings.log_db_path)
    anthropic_client = None
    if settings.anthropic_api_key:
        try:
            import anthropic

            anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        except Exception:
            anthropic_client = None
    broker = AlpacaBroker(
        api_key=alpaca.alpaca_api_key,
        secret_key=alpaca.alpaca_secret_key,
        paper=alpaca.alpaca_paper,
        trading_allowed=alpaca.trading_allowed,
    )
    return cache, store, anthropic_client, broker


cache, store, anthropic_client, broker = get_components()

if "scheduler" not in st.session_state:
    st.session_state.scheduler = BotScheduler()
if "last_record" not in st.session_state:
    st.session_state.last_record = None


# ---------- Cabecera y disclaimer ----------
st.title("📈 Trading Bot Agéntico + Alpaca")
mode = "PAPER (simulado)" if alpaca.alpaca_paper else ("REAL ⚠️" if alpaca.is_live else "BLOQUEADO")
st.warning(
    "**Proyecto demostrativo — NO es asesoramiento financiero.** "
    f"Modo actual: **{mode}**. "
    "Para operar con dinero real se requieren `ALPACA_PAPER=false` Y `ENABLE_LIVE_TRADING=true`."
)

# ---------- Panel de control (sidebar) ----------
with st.sidebar:
    st.header("Panel de control")
    query = st.text_input("Consulta (lenguaje natural)", "tech de mediana capitalización infravalorada con momentum positivo")
    threshold = st.slider("Umbral de score para comprar", 0.0, 10.0, settings.default_score_threshold, 0.1)
    interval = st.number_input("Intervalo (min)", min_value=5, max_value=1440, value=settings.default_interval_minutes)
    max_pct = st.slider("Máx % del portfolio por posición", 0.01, 0.20, settings.default_max_position_pct, 0.01)
    max_positions = st.number_input("Máx posiciones abiertas", min_value=1, max_value=50, value=settings.default_max_open_positions)

    if not anthropic_client:
        st.info("Sin ANTHROPIC_API_KEY: el screener usa el parser/razonamiento de respaldo (heurístico).")
    if not broker.connected:
        st.info("Sin claves de Alpaca: las órdenes se simulan (no se ejecutan).")

    config = BotConfig(
        query=query, score_threshold=threshold, max_position_pct=max_pct,
        interval_minutes=int(interval), max_open_positions=int(max_positions),
        paper=alpaca.alpaca_paper, live_trading_enabled=alpaca.enable_live_trading,
    )
    bot = TradingBot(
        config=config, broker=broker, cache=cache, store=store,
        anthropic_client=anthropic_client,
        planner_model=settings.model_planner, reasoner_model=settings.model_reasoner,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Ejecutar ahora", use_container_width=True):
            with st.spinner("Ejecutando ciclo..."):
                st.session_state.last_record = bot.run_once()
            st.success("Ciclo completado.")
    with col2:
        if not st.session_state.scheduler.running:
            if st.button("⏱️ Activar bot", use_container_width=True):
                st.session_state.scheduler.start(
                    bot, int(interval),
                    on_run=lambda rec: st.session_state.__setitem__("last_record", rec),
                )
                st.success(f"Bot activo (cada {interval} min).")
        else:
            if st.button("⏸️ Pausar bot", use_container_width=True):
                st.session_state.scheduler.stop()
                st.info("Bot pausado.")

    st.caption(f"Estado: {'🟢 activo' if st.session_state.scheduler.running else '⚪ inactivo'}")


# ---------- Cuerpo: cuenta, posiciones, órdenes, equity, logs ----------
account = broker.get_account()
positions = broker.get_positions()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Equity", f"${account.equity:,.0f}")
m2.metric("Cash", f"${account.cash:,.0f}")
m3.metric("Buying power", f"${account.buying_power:,.0f}")
m4.metric("Posiciones", len(positions))

tab_pos, tab_ord, tab_eq, tab_screen, tab_logs = st.tabs(
    ["📊 Posiciones", "🧾 Órdenes", "📈 Equity", "🔎 Screening", "🪵 Logs / Traza"]
)

with tab_pos:
    if positions:
        df = pd.DataFrame([p.model_dump() for p in positions])
        df["unrealized_plpc"] = (df["unrealized_plpc"] * 100).round(2)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.write("Sin posiciones abiertas.")

with tab_ord:
    orders = store.get_orders()
    if orders:
        st.dataframe(
            pd.DataFrame([o.model_dump() for o in orders]), use_container_width=True, hide_index=True
        )
    else:
        st.write("Aún no hay órdenes registradas.")

with tab_eq:
    curve = store.get_equity_curve()
    if curve:
        df = pd.DataFrame([c.model_dump() for c in curve])
        fig = go.Figure(go.Scatter(x=df["timestamp"], y=df["equity"], mode="lines+markers"))
        fig.update_layout(title="Equity curve", height=400, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Sin histórico de equity todavía.")

with tab_screen:
    rec = st.session_state.last_record
    if rec is None:
        st.write("Ejecuta un ciclo para ver el ranking y el razonamiento.")
    else:
        st.subheader("Ranking de candidatos")
        if rec.decisions:
            st.dataframe(
                pd.DataFrame([d.model_dump() for d in rec.decisions]),
                use_container_width=True, hide_index=True,
            )
        sel = st.selectbox("Ver gráfico de velas de:", [d.ticker for d in rec.decisions] or [""])
        if sel:
            try:
                import yfinance as yf

                h = yf.Ticker(sel).history(period="6mo", auto_adjust=True)
                if not h.empty:
                    fig = go.Figure(
                        go.Candlestick(
                            x=h.index, open=h["Open"], high=h["High"], low=h["Low"], close=h["Close"]
                        )
                    )
                    fig.add_trace(go.Scatter(x=h.index, y=h["Close"].rolling(50).mean(), name="SMA50"))
                    fig.add_trace(go.Scatter(x=h.index, y=h["Close"].rolling(200).mean(), name="SMA200"))
                    fig.update_layout(title=f"{sel}", height=450, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as exc:  # noqa: BLE001
                st.caption(f"No se pudo cargar el gráfico: {exc}")

with tab_logs:
    rec = st.session_state.last_record
    if rec is None:
        st.write("Sin ejecuciones en esta sesión.")
    else:
        st.write(f"**Run {rec.run_id}** — {rec.timestamp}")
        st.write(f"Coste estimado IA: ${rec.token_usage.get('estimated_cost_usd', 0)}")
        if rec.errors:
            st.error("\n".join(rec.errors))
        st.json(rec.model_dump(mode="json"))
