# Source Harvester — Deployment Runbook (Container-first)

This document describes how to deploy, operate, and roll back the Source Harvester microservice without Kubernetes. It assumes Docker is available on the target host.

## 1. Artifacts
- Container image: built by CI and pushed to your registry (e.g., GHCR)
  - Example: `ghcr.io/<owner>/source-harvester:<version>` and `:latest`
- Alembic migrations embedded in the repo; run from the container or host Python if desired

## 2. Configuration
- Env variables (env-only)
  - `SH_ENVIRONMENT` — `dev|test|staging|prod`
  - `SH_CONFIG_FILE` — path to YAML config (optional; defaults to `configs/default.yaml` in image)
  - `SH_API_BEARER_TOKEN` — bearer token (required for POST, and for GET in prod)
  - Provider keys (set any that apply):
    - `SH_SERPER_KEY`
    - `SH_GOOGLE_API_KEY`, `SH_GOOGLE_CSE_ID`
    - `SH_BRAVE_KEY`
  - LLM keys: `OPENAI_API_KEY` (or `SH_OPENAI_API_KEY`)
  - DB URL: `SH_DATABASE_URL` (e.g., `postgresql+asyncpg://user:pass@host:5432/dbname`)
- Optional Gunicorn tunables
  - `WEB_CONCURRENCY` (default ~ CPU/2)
  - `GUNICORN_TIMEOUT` (default 30)
  - `GUNICORN_LOGLEVEL` (info|debug)

See `.env.example` for a starter env file.

## 3. Database Migrations
- One-time or per-deploy:
  - `ALEMBIC_SQLALCHEMY_URL=$SH_DATABASE_URL alembic upgrade head`
- From within a container instance:
  - `docker run --rm --env-file /etc/source-harvester.env <image> alembic upgrade head`

## 4. Deployment Options

### 4.1 Docker Compose (recommended for single host)
- `docker compose up --build -d`
- Health: `curl -fsS http://localhost:${PORT:-8000}/healthz | jq`
- Logs: `docker compose logs -f app`
- Update:
  - `docker compose pull && docker compose up -d` (roll forward)
  - For rollback, pin desired tag in `compose.yaml` and re-run `up -d`

### 4.2 systemd + Docker (no Compose)
- Unit file example: `deploy/systemd/source-harvester.service`
- Env file: `/etc/source-harvester.env` with the variables above
- Commands:
  - `systemctl daemon-reload`
  - `systemctl enable --now source-harvester`
  - `systemctl status source-harvester`

## 5. Observability
- Logs: JSON to stdout/stderr. Capture with host log collector (journald, fluent-bit, etc.)
- Healthcheck: `/healthz` (DB ping + outbound probe)
- Metrics: HTTP client telemetry hooks record request/response counts and durations (extend to your metrics backend if needed)

## 6. Scaling
- Vertical: set `WEB_CONCURRENCY` based on CPU/memory
- Horizontal: multiple replicas with a reverse proxy (NGINX/Traefik) in front; keep service stateless

## 7. Security
- Enforce bearer token for POST in all environments, and GET in `prod`
- Store secrets only in env; rotate by updating env and restarting the service
- Place behind a trusted proxy for TLS and rate limiting

## 8. Rollback
- Keep previous image tags available
- `docker compose pull <previous-tag> && docker compose up -d`
- or `docker run` the previous tag with the same env file

## 9. Troubleshooting
- `500` from providers: the service retries 429/5xx with backoff; verify provider quotas/keys
- DB issues: check `SH_DATABASE_URL` and run Alembic; `/healthz.checks.db` should be `true`
- Auth failures: verify `Authorization: Bearer <token>` and `SH_API_BEARER_TOKEN`

