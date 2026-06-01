# Proyectos

Monorepo con mis proyectos, organizados por carpetas. Aquí se irán
añadiendo los nuevos proyectos que desarrolle.

## Índice

| Carpeta | Proyecto | Descripción | Stack |
|---|---|---|---|
| [`tfg/`](./tfg) | Sentiment Analysis para predicción bursátil | TFG: sistema de análisis de sentimiento sobre noticias financieras para predecir movimientos de bolsa (web scraping, FinBERT vs VADER, dataset y modelos LSTM/GRU). | Python, NLP, ML |
| [`machine-learning/parkinson/`](./machine-learning/parkinson) | Detección de Parkinson por imagen | Clasificación de dibujos (espirales/ondas) para detección de Parkinson con SVM + HOG, servida con Streamlit. | Python, scikit-learn, Streamlit |
| [`agentes/trading-bot/`](./agentes/trading-bot) | Trading bot agéntico + Alpaca | Screener de acciones con razonamiento (SDK Anthropic, tool use) que filtra/puntúa candidatos y ejecuta órdenes en Alpaca (paper). Demostrativo, no asesoramiento. | Python, Anthropic, Alpaca, Streamlit |

## Estructura

```
.
├── tfg/                      # Trabajo de Fin de Grado (sentiment analysis bursátil)
├── machine-learning/
│   └── parkinson/            # Detección de Parkinson por imagen (SVM + HOG)
└── agentes/
    └── trading-bot/          # Trading bot agéntico (screener + Alpaca paper)
```

## Cómo ejecutar cada proyecto

Cada carpeta incluye su propio README/instrucciones. Por ejemplo, el
proyecto de Parkinson se lanza con:

```bash
cd machine-learning/parkinson
python -m streamlit run app.py
```
