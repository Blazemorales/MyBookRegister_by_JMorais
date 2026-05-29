FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libpq-dev + build-essential cobrem asyncpg e qualquer wheel ausente.
# Mantemos enxuto via --no-install-recommends e limpando o apt cache.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# 1 worker é o pacto: rooms/sessions do Socket.IO moram em memória do processo.
# Para escalar horizontalmente, ligar AsyncRedisManager + sticky session no proxy.
CMD ["uvicorn", "backend_api:asgi", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--loop", "uvloop", "--http", "httptools", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
