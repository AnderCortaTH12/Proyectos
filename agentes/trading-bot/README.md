# Trading Bot Agéntico + Alpaca

Bot de trading **demostrativo** que combina un *screener de acciones con
razonamiento* (agente con el SDK de Anthropic) y la ejecución automática de
órdenes en **Alpaca** (paper trading por defecto).

El usuario escribe una consulta en lenguaje natural
(p. ej. *"tech de mediana capitalización infravalorada con momentum positivo"*),
el sistema la interpreta, recopila datos reales, filtra y puntúa candidatos,
justifica cada elección anclada a los datos, y —si el score supera un umbral—
ejecuta una orden respetando reglas de gestión de riesgo.

El **broker es enchufable** (patrón template): por defecto usa un **MockBroker**
100% local (cartera simulada de $100k, **sin credenciales ni dinero real**), y
opcionalmente un **AlpacaBroker** (paper). Puedes probar el bot de extremo a
extremo sin ninguna API key de broker.

> ## ⚠️ Disclaimer
> Proyecto **educativo / de portfolio**. **NO es asesoramiento financiero** ni
> una recomendación de inversión. Las heurísticas de puntuación son
> deliberadamente simples. Opera por defecto en **paper trading** (dinero
> ficticio). Operar con dinero real es responsabilidad exclusiva del usuario y
> requiere activar dos cerrojos a la vez (ver más abajo). El autor no se
> responsabiliza de pérdidas.

## Arquitectura

Diagrama completo en [`docs/architecture.mmd`](docs/architecture.mmd) (Mermaid).

```
Consulta NL
   │
   ▼
Planner (Haiku, tool use) ──► ScreenCriteria (Pydantic)
   │
   ▼
Universo S&P 500 ─► Descarga paralela (asyncio) ─► Caché DuckDB (TTL)
   │                     │
   │             fundamentals / technicals / benchmarks
   ▼
Filtros duros ─► Scoring 0–10 ─► Top-N
   │
   ▼
Reasoner (Sonnet) ─► Guardrail (verifica que cada número citado existe)
   │
   ▼
Risk management (máx 5% por posición, anti-duplicado) ─► Alpaca (paper)
   │
   ▼
Streamlit: posiciones, P&L, órdenes, equity curve, logs/traza del agente
```

### Módulos

| Módulo | Responsabilidad |
|---|---|
| `screener/parser/` | Consulta NL → `ScreenCriteria` (Haiku + tool use; fallback heurístico). |
| `screener/tools/` | `get_universe`, `get_fundamentals`, `get_technicals`, benchmarks. Caché DuckDB + backoff. |
| `screener/engine/` | Filtros duros y puntuación ponderada 0–10. |
| `screener/reasoning/` | Justificación (Sonnet) + **guardrail** anti-alucinaciones numéricas. |
| `broker/` | Interfaz abstracta `BrokerInterface` (template), `MockBroker` (simulado, por defecto), `AlpacaBroker` (paper) y gestión de riesgo (sizing, duplicados). |
| `bot/` | Orquestador (screening→decisión→ejecución) y scheduler periódico (APScheduler). |
| `store/` | Persistencia en DuckDB: ejecuciones, órdenes, equity curve. |
| `app.py` | UI Streamlit. |

## Instalación

Con **uv** (recomendado):

```bash
uv venv && source .venv/bin/activate    # en Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

O con venv + pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y rellena las claves:

```bash
cp .env.example .env
```

- `ANTHROPIC_API_KEY`: tu clave de Anthropic. (Sin ella, el screener usa un
  parser/razonamiento de respaldo heurístico, sin IA.)
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`: claves de **paper** de Alpaca
  (créalas en https://app.alpaca.markets/). Sin ellas, las órdenes se simulan.

## Ejecución

```bash
streamlit run app.py
```

Abre http://localhost:8501. Escribe una consulta, ajusta el umbral de score y
pulsa **Ejecutar ahora** o **Activar bot** (ejecución periódica).

Con Docker:

```bash
docker build -t trading-bot .
docker run --env-file .env -p 8501:8501 trading-bot
```

## Brokers (template + MockBroker)

El bot habla con cualquier broker que implemente `BrokerInterface`
(`get_account`, `get_positions`, `get_orders`, `place_order`):

- **`MockBroker` (por defecto):** cartera simulada en memoria con $100k. Simula
  las ejecuciones a precio de mercado, calcula P&L en tiempo real y **no se
  conecta a ningún broker real ni usa credenciales**. Ideal para demo y tests.
- **`AlpacaBroker` (opcional):** ejecuta en Alpaca (paper por defecto). Requiere
  claves; ver más abajo.

En la UI puedes cambiar de broker con el selector del panel lateral. El
predeterminado es el simulado.

## Paper vs. dinero real (doble cerrojo, solo AlpacaBroker)

Por seguridad, para enviar órdenes **reales** no basta con desactivar paper:

```env
ALPACA_PAPER=false
ENABLE_LIVE_TRADING=true   # ambas a la vez
```

Si falta cualquiera de las dos, el broker **bloquea** las órdenes reales y solo
las simula (estado `SIMULATED`), registrándolas en el log.

## Gestión de riesgo

- **Máximo 5% del portfolio por posición** (configurable, tope duro al 20%).
- **No duplica posiciones**: si ya hay posición en el ticker, se descarta.
- Respeta un máximo de posiciones abiertas y el *buying power* disponible.
- Solo se ejecutan órdenes cuya justificación **supera el guardrail**.

## Tests

```bash
pytest
```

Incluye tests de gestión de riesgo, wrapper de Alpaca (con mocks, sin red),
ciclo del bot (screening mockeado) y screener (filtros, scoring, planner
heurístico y guardrail).

## Notas sobre licencia de datos

- **yfinance** obtiene datos de Yahoo Finance y **no está pensado para uso
  comercial**; úsalo solo con fines personales/educativos y respeta los
  términos de Yahoo.
- Los constituyentes del S&P 500 se leen de Wikipedia (CC BY-SA).
- "S&P 500" es una marca de S&P Dow Jones Indices.

## Estructura

```
trading-bot/
├── app.py
├── config/{settings.py, alpaca.py}
├── docs/architecture.mmd
├── src/trading_bot/
│   ├── models.py, telemetry.py, logging_conf.py
│   ├── screener/{parser, tools, engine, reasoning, screen.py, models.py}
│   ├── broker/{alpaca_client.py, risk.py}
│   ├── bot/{trading_bot.py, scheduler.py}
│   └── store/trade_log.py
└── tests/
```
