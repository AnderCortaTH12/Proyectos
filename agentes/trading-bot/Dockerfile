FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema mínimas (para numpy/pandas-ta wheels suele bastar slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/src
EXPOSE 8501

# Lanza la UI de Streamlit
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
