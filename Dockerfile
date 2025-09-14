# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN python -m pip install --upgrade pip wheel setuptools \
 && python -m pip wheel --wheel-dir /wheels .

# --- Runtime image ---
FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels source-harvester \
 && rm -rf /wheels

# Install curl for simple healthcheck
RUN apt-get update -y && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY configs ./configs
COPY gunicorn_conf.py ./gunicorn_conf.py

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT:-8000}/healthz || exit 1

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]

