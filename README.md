# Source Harvester Microservice

[![CI](https://github.com/hopchouinard/1-source_harvester/actions/workflows/ci.yml/badge.svg)](https://github.com/hopchouinard/1-source_harvester/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-ASGI-brightgreen)
[![Container](https://img.shields.io/badge/Container-GHCR-informational)](https://ghcr.io/hopchouinard/source-harvester)

Minimal FastAPI microservice scaffolding for the Source Harvester, following the implementation plan in `specs/SH_Microservice_Plan.md`.

- Runtime: Python 3.13
- API: FastAPI (ASGI)
- Tests: pytest, pytest-asyncio, httpx

For development, install dependencies (via Poetry or uv), then run tests:

```
poetry env use 3.13
poetry install
poetry run pytest
```

This repository is being implemented phase-by-phase per the plan. Current status: Phase M — Packaging & CI ready.

## Quickstart
- Install deps and set Python 3.13: `make install`
- Run the API with reload: `make run` (defaults to port 8000)
- Run tests: `make test`

Then visit `http://localhost:8000/healthz` or try:

```
curl -s http://localhost:8000/healthz | jq
```

## Makefile Usage
- `make install` — setup Poetry env and install deps
- `make run` — start `uvicorn app.main:app` with `--reload`
- `make test` — run `pytest`
- `make coverage` — run tests with coverage
- `make lint` / `make format` — Ruff check/fix and Black format
- `make typecheck` — mypy
- `make migrate DB_URL=sqlite:///dev.db` — apply Alembic migrations

## Configuration (Phase B)
- YAML: `configs/default.yaml` is loaded by default. Override via `SH_CONFIG_FILE=/path/to/config.yaml`.
- Env overrides: use nested variables, e.g. `SH_SEARCH__PROVIDER=google`, `SH_LLM__PROVIDER=openai`.
- Secrets (env only):
  - Providers: `SH_SERPER_KEY`, `SH_GOOGLE_API_KEY`, `SH_GOOGLE_CSE_ID`, `SH_BRAVE_KEY`
  - LLM: `OPENAI_API_KEY` (or `SH_OPENAI_API_KEY`)
- Secret enforcement: enforced in `prod` or when `SH_VALIDATE_SECRETS=true`.

## CI
- GitHub Actions runs lint (Ruff), format check (Black), type-check (mypy), and tests (pytest) on pushes and PRs. See the CI badge above for status.

## Docker
- Build image: `docker build -t source-harvester:local .`
- Run: `docker run --rm -p 8000:8000 -e SH_ENVIRONMENT=dev source-harvester:local`
- Health: `curl http://localhost:8000/healthz`

## Docker Compose (local dev)
- Start (build + run with reload): `docker compose up --build`
- Stop and remove: `docker compose down -v`
- Logs: `docker compose logs -f app`
- The service exposes `http://localhost:${PORT:-8000}/healthz` and reloads on code changes.

Gunicorn config (gunicorn_conf.py)
- Tunables via env:
  - `WEB_CONCURRENCY` (default ~ CPU/2)
  - `GUNICORN_TIMEOUT` (default 30)
  - `GUNICORN_LOGLEVEL` (info|debug)

## CI Images (tags)
- On tags, CI builds and pushes to GHCR:
  - `ghcr.io/<owner>/source-harvester:<tag>` and `:latest`
