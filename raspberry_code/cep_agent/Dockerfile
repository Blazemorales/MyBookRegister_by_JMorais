FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY raspberry_code/cep_agent/requirements.txt ./raspberry_code/cep_agent/requirements.txt
RUN pip install -r raspberry_code/cep_agent/requirements.txt

# jobs/diario.py e jobs/mensal.py importam CEP/respostas.py subindo
# parents[3] a partir de jobs/ — preserva a mesma profundidade relativa
# do clone completo do repo usado na Raspberry Pi.
COPY cep_code/backend/CEP ./cep_code/backend/CEP
COPY raspberry_code/cep_agent ./raspberry_code/cep_agent

WORKDIR /app/raspberry_code/cep_agent

EXPOSE 8080

# Render injeta a porta via $PORT; fallback 8080 para execução local.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
