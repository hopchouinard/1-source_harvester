## Summary

This PR delivers the full Source Harvester microservice per plan (Phases A–O), including core domain + LLM rewrite, adapters + HTTP infra, orchestrator + persistence, API endpoints, observability + security, robust tests with coverage, and container-first packaging/CI/deployment. Phase N replaces K8s with Docker/Compose/systemd and provides a runbook, CI pipelines, and image publishing to GHCR/Docker Hub.

## Evidence

- Tests: all green; coverage ~91%
- Acceptance: warm path p95 < 500ms (mocked providers, cached rewrite); DB invariants validated
- Health: /healthz reports DB/HTTP checks
- CI: lint/type/test on PRs; Postgres + Testcontainers; image build/publish to GHCR/Docker Hub

## Test Coverage

- New/updated tests:
  - Unit: schema/validation/placeholders, HTTP client infra, adapters, repositories
  - Integration: orchestrator→adapters→DB, Alembic migration
  - E2E: full POST→persist→GET flows; error mapping
  - Property: placeholders and merge/dedupe invariants
  - DB: Testcontainers Postgres in CI; SQLite locally
  - Acceptance: warm-path p95, DB invariants
- Manual steps:
  - Local Docker: `docker build -t source-harvester:local . && docker run --rm -p 8000:8000 -e SH_ENVIRONMENT=dev source-harvester:local`
  - Local Compose: `docker compose up --build`
  - Health: `curl http://localhost:8000/healthz`

## Risks & Rollback

- Risk: ☐ low ☒ medium ☐ high
  - Provider behavior/quotas and DB sizing in production remain the main risks; retries/backoff and error mapping are implemented.
- Rollback plan:
  - Revert to previous tags; schema is initial; adapters can be disabled with env

## Checklists

- [x] Unit tests green
- [x] Lint green
- [x] Docs updated (if user-facing or API surface changed)
- [x] Security checklist completed (auth/secrets impacted)
- [x] Migration checklist completed (initial schema)
- [x] Perf checklist completed (acceptance p95 warm path)

Fixes: #
Follows up: #
Owners: @hopchouinard
