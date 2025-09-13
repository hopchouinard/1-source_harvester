# Source Harvester Microservice — Implementation Plan (v1)

This plan turns the spec in `specs/SH_Microservice_Spec.md` into a concrete, buildable roadmap. It captures architecture, contracts, sequencing, and task breakdown to deliver a minimal, robust, and testable service.

---

## 0) Scope & Outcomes

- Purpose: Given a natural-language query, generate a provider‑neutral schema via LLM, expand placeholders, call one or more web search providers, merge + dedupe URLs, persist raw and processed results, and return the processed list.
- Non‑goals: Crawling, parsing, summarization, ranking beyond overlap‑based confidence, scheduling/orchestration.
- Interfaces: REST only. Stateless per request. DB persistence as specified.
- Process: TTD (tests‑first) across all phases with unit, integration (cross‑phase), and end‑to‑end (E2E) tests executed continuously.
- Acceptance: Matches spec’s error semantics, latency targets, DB invariants, and guardrails. A phase is complete only when all tests (unit, integration, E2E) are passing; the project is complete only when the full test suite is green.

---

## 0.1) TTD Methodology & Quality Gates

- Tests‑first: For each phase, write failing tests before implementation.
- Multi‑level coverage: Include unit tests, integration tests spanning boundaries between the current and prior phases, and an E2E test path.
- Phase exit criteria:
  - All new and existing unit tests pass.
  - Cross‑phase integration tests pass (no regressions at boundaries).
  - E2E smoke/regression suite passes for the user‑visible flows touched by the phase.
- Project completion criteria: Entire unit + integration + E2E suites are green in CI, with acceptance checks met.

---

## 1) Architecture Summary

- Runtime: Python 3.12, FastAPI (ASGI) with Uvicorn (behind Gunicorn in container).
- HTTP client: httpx (async), retries/backoff/jitter on 429/5xx.
- LLM: Config‑driven client (OpenAI/Anthropic/Gemini/local), prompt on disk, strict JSON validation.
- Domain: Provider‑neutral schema + placeholder whitelist/expansion.
- Providers: Pluggable adapters for Serper, Google CSE, Brave.
- Orchestrator: Greedy by default; forced single provider by config; merge + dedupe + confidence.
- Persistence: PostgreSQL via SQLAlchemy (async) + Alembic migrations.
- Config: YAML + env (pydantic‑settings). Secrets via env only.
- Observability: JSON logs, metrics hooks, /healthz.
- Security: Internal bearer/mTLS (start with bearer). Limits enforced.

---

## 2) Minimal Module Layout

```
app/
  main.py                 # FastAPI app, routes (/search-runs, /search-runs/:id, /healthz)
  config.py               # pydantic-settings + YAML loader
  models.py               # SQLAlchemy tables + alembic migration stubs
  adapters/
    base.py               # SearchProviderAdapter interface
    serper.py             # Serper adapter
    google.py             # Google CSE adapter
    brave.py              # Brave adapter
  llm/
    client.py             # provider-agnostic LLM client
    prompts/              # rewrite_query.txt (from config path)
  core/
    schema.py             # Provider-neutral schema (Pydantic)
    placeholders.py       # whitelist + expansion
    orchestrator.py       # greedy/forced orchestration, merge/dedupe, confidence
    validation.py         # strict JSON + placeholder validation
    hashing.py            # URL dedupe hash (e.g., SHA1(url))
  db/
    session.py            # async session helpers
    queries.py            # cache lookup/insert, run inserts
  observability/
    logging.py            # structlog/loguru setup
    metrics.py            # counters/timers (pluggable)
```

---

## 3) External Contracts

- REST Endpoints
  - POST `/search-runs` → 201 on success; 400 invalid schema/placeholders; 502 LLM failure; 502 all providers failed.
  - GET `/search-runs/{id}` → 200 with metadata and processed results.
  - (Optional) GET `/search-runs?query=...&from=...&to=...` listing.
- DB Schema (Postgres)
  - `queries(id, original_query UNIQUE, rewritten_template, created_at)`
  - `search_runs(id, query, rewritten_template, run_timestamp, config JSONB, providers_used TEXT[])`
  - `search_results_raw(id, run_id FK, provider, url, rank, meta JSONB, inserted_at)`
  - `search_results_processed(id, run_id FK, url, providers TEXT[], confidence INT, dedupe_hash TEXT, inserted_at)`
  - Indexes: `UNIQUE (run_id, dedupe_hash)`; `INDEX (run_id, provider)`
- Provider Adapters
  - Interface: `search(schema, options?) -> SearchResult { provider, queryUsed, urls[], meta? }`
  - Implementations: Serper, Google CSE, Brave.

---

## 4) Detailed Tasks by Phase

### Phase A — Project Scaffolding & Tooling

- Initialize project with Poetry/uv and lock dependencies (FastAPI, httpx, pydantic v2, SQLAlchemy 2, asyncpg, Alembic, structlog/loguru, ruff, black, pytest, pytest-asyncio, respx).
- Create base module layout (see section 2).
- TTD: add failing tests first for `/healthz` and basic app startup; implement until green.
- Configure lint/format/type checks (ruff, black, pyright or mypy) and pre-commit if used.
- Establish E2E harness scaffolding (pytest + httpx TestClient + Postgres fixture + provider/LLM mocks).

### Phase B — Configuration & Settings

- Implement `config.py` using pydantic‑settings to load env + YAML.
- YAML schema: `search.provider`, `search.cascade_order`, `search.default_options`, `llm.*`.
- Validate presence of required env secrets (SERPER_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, BRAVE_KEY, OPENAI_API_KEY as applicable).
- Expose resolved prompt path and load bytes with hashing (for audit logging).
- TTD: unit tests for YAML parsing, env override precedence, and secret presence; integration test that app boot reads config; E2E smoke asserts `/healthz` and config‑dependent flags.

### Phase C — Core Domain Models

- Implement Pydantic model for Provider‑Neutral Query:
  - `keywords: list[str]` (non‑empty), `boolean: Literal["AND","OR"]|None` (default AND), `filters` with `sites, date_after, date_before, lang, geo, max_results`.
- Implement strict extra‑forbid behavior (reject unknown fields).
- Implement placeholder whitelist tokens and validator for date fields.
- Implement runtime placeholder expander using system clock; reject unknown/leftover.
- TTD: unit/property tests for schema validation, placeholders (valid/invalid), limits; integration test for validation path through API schema models when wired.

### Phase D — LLM Rewriter

- Implement `llm/client.py` with pluggable provider (OpenAI first):
  - Reads prompt file from config, sends user query and rules, temperature 0.0, max tokens ≤ 512.
  - Enforces timeout (5s) and maps failures to 502.
- Parse LLM output as JSON; validate against Pydantic schema; run placeholder validator (hard‑fail 400 on violations).
- Cache `original_query → rewritten_template` in `queries` table (see Phase F) with placeholders preserved.
- TTD: unit tests for client timeouts/error mapping; contract tests with fixed JSON; integration tests for cache lookup/miss behavior (with DB fixture); E2E smoke hitting POST with mocked LLM to validate 201 payload shape.

### Phase E — HTTP Client Infra

- Create shared httpx `AsyncClient` with sane defaults: timeouts (3–4s), retry/backoff with jitter for 429/5xx, headers, telemetry hooks.
- Add request/response logging with run_id correlation (debug‑level obfuscated as needed).
- TTD: unit tests for retry/backoff policy; integration tests verifying telemetry hooks called during adapter requests (with respx).

### Phase F — Persistence Layer

- Define SQLAlchemy models or Core tables per spec in `models.py`.
- Initialize Alembic and create migration for initial schema.
- Implement `db/session.py` for async engine/session creation from env.
- Implement `db/queries.py` repositories:
  - `get_cached_rewritten_template(original_query)`
  - `insert_query_cache(original_query, rewritten_template)`
  - `insert_search_run(query, rewritten_template, config, providers_used) -> run_id`
  - `bulk_insert_raw(run_id, rows)`
  - `bulk_insert_processed(run_id, rows)`
  - `get_run(run_id)` and `list_runs(filters)`
- TTD: unit tests for repositories (using transaction rollbacks/fixtures); integration tests for Alembic migrations and unique index constraints; E2E confirms DB rows match acceptance counts.

### Phase G — Provider Adapters

- Define `adapters/base.py` interface: name + `search(schema, options) -> SearchResult`.
- Implement Serper adapter:
  - Endpoint: `POST https://google.serper.dev/search` with API key header.
  - Build query string from neutral schema (keywords + boolean, `site:` filters; `after:/before:` if supported; map lang/geo if supported).
  - Parse response URLs and optional rank.
- Implement Google CSE adapter:
  - Endpoint: `GET https://www.googleapis.com/customsearch/v1` with `key`, `cx`.
  - Build params including `q`, `lr`/`gl` if applicable; apply site constraints.
  - Collect URLs, ranks.
- Implement Brave adapter:
  - Endpoint: `GET https://api.search.brave.com/res/v1/web/search` with API key header.
  - Build params; apply freshness via provider‑specific param (ignore explicit after/before per spec).
  - Collect URLs, ranks.
- For each adapter: unit tests with respx mocks; include `queryUsed` for observability.
- TTD: write adapter tests first (success/timeout/429 backoff); integration tests for orchestrator→adapter boundary with mocks; run E2E with multiple providers mocked to validate merge inputs.

### Phase H — Orchestrator & Merge/Dedupe

- Implement provider resolution: forced (`search.provider != "auto"`) vs greedy (iterate `cascade_order`).
- For each chosen provider: compile provider query/params, call adapter, collect `{provider, queryUsed, urls, meta}`.
- Merge outputs:
  - Union of URLs; `providers` = set of providers that returned each URL.
  - `confidence` = count of distinct providers.
  - `dedupe_hash` = SHA1(url) or stable normalized hash.
- Persist snapshots: raw rows (provider, url, rank, meta) and processed rows.
- Return processed list, providers_used, and final per‑provider `queryUsed` in response meta.
- TTD: unit tests for merge/dedupe/hashing invariants; integration tests spanning adapters+DB; E2E verifying confidence equals distinct provider count and persistence invariants.

### Phase I — API Endpoints

- POST `/search-runs`:
  - Input: `{ query: str, options?: { lang?, maxResults? } }`.
  - Flow: check cache → LLM if miss → validate/expand placeholders → orchestrate providers → persist → return 201 with processed payload per spec.
  - Errors: map LLM failure to 502; invalid schema/placeholders to 400; all providers failed to 502.
- GET `/search-runs/{id}`: fetch metadata and processed results.
- GET listing (optional): filter by `query`, `from`, `to`.
- TTD: route tests first (happy path and errors 400/502); integration tests with DB + mocks; E2E validates full POST→persist→GET cycle.

### Phase J — Observability & Health

- Logging: structlog/loguru JSON logs with `run_id`, timings, `queryUsed`, counts, errors.
- Metrics: counters and histograms for provider latency, success rate, URLs returned, overlap distribution, error types.
- `/healthz`: DB ping + outbound DNS/HTTP probe to a harmless endpoint; return 200 on OK.
- TTD: unit tests for log formatting and redaction; integration tests for metrics emission; E2E probes `/healthz` and inspects basic readiness behavior.

### Phase K — Security & Limits

- Add bearer auth middleware for POST routes; permit GETs based on environment (internal use).
- Secrets only via env; ensure keys not emitted in logs.
- Enforce limits: final query length ≤ 512, keywords ≤ 12, sites ≤ 20 (configurable); validate early.
- TTD: unit tests for limit validators and auth; integration tests for auth middleware + route protection; E2E verifies unauthorized requests are rejected.

### Phase L — Testing Strategy (TTD)

- Apply TTD at every phase: write failing tests first, implement to green, keep all prior tests green.
- Unit tests: placeholder expansion, schema validation (valid/invalid), LLM client (mock), provider adapters (respx), merge/dedupe, repositories.
- Integration tests: cross‑phase boundaries (e.g., API→orchestrator→DB), POST happy path (with mocked LLM + providers), partial provider failure, all providers failure, invalid placeholder.
- E2E tests: hit real FastAPI app (TestClient) with DB fixture and mocked externals; validate response payloads and DB side‑effects. Run E2E after each phase completes.
- DB tests: using Testcontainers/Postgres or pytest‑postgresql; Alembic migration smoke test.
- Property tests: placeholder tokens and merge/dedupe invariants.
- Quality gate: Do not proceed to the next phase unless all unit, integration, and E2E tests are passing.

### Phase M — Packaging, CI, and Docker

- Dockerfile (multi‑stage, slim), gunicorn worker config, non‑root user.
- GitHub Actions (or equivalent): lint, type check, unit + integration tests, build image, push tag.
- Versioning: SemVer image tags `source-harvester:<version>`.

### Phase N — Deployment & Runbook

- K8s manifests or Helm values (config maps, secrets, resources, readiness/liveness to `/healthz`).
- Ingress (NGINX/Envoy). Configure timeouts aligned with service.
- Runbook: env vars, config YAML, rotating secrets, quota/backoff handling.

### Phase O — Acceptance Criteria Verification

- Verify response times (P95) with synthetic tests; ensure warm cache path meets target.
- Validate DB row counts and uniqueness invariants after a run.
- Confirm error taxonomy and codes for each failure mode.
- Confirm downstream fetchers can rely on `search_results_processed` keyed by `run_id`.

---

## 5) Task Backlog (Actionable Checklist)

- TTD Quality Gates (apply to each phase)
  - [ ] Write failing unit/integration tests first for the phase scope
  - [ ] Implement until unit + integration are green without regressions
  - [ ] Run E2E smoke/regression; fix until green
  - [ ] Only then proceed to the next phase

- Repo scaffolding and dependencies
  - [ ] Initialize project (Poetry/uv), add core deps and dev tools
  - [ ] Create module layout (folders, __init__.py where needed)
  - [ ] Add basic FastAPI app with `/healthz`
- Config & env
  - [ ] Implement `config.py` with pydantic‑settings
  - [ ] YAML loader + schema; env overrides; secrets validation
  - [ ] Load prompt file path + hash
- Core domain
  - [ ] Pydantic models for provider‑neutral schema (extra=forbid)
  - [ ] Placeholder whitelist and validator
  - [ ] Placeholder runtime expander
  - [ ] Limits validation (length, keywords, sites)
- LLM client
  - [ ] Implement OpenAI client (timeout, 5s); temperature 0.0
  - [ ] Parse JSON strictly; map failures to 502
  - [ ] Validation pipeline: schema → placeholders
  - [ ] Unit tests with mocked responses
- Persistence
  - [ ] Define SQLAlchemy models/tables per spec
  - [ ] Alembic setup + initial migration
  - [ ] Async engine/session helpers
  - [ ] Repositories: cache, run insert, bulk raw/processed, getters
- Provider adapters
  - [ ] Base interface and types
  - [ ] Serper adapter (query build, call, parse)
  - [ ] Google CSE adapter (params, call, parse)
  - [ ] Brave adapter (freshness param, call, parse)
  - [ ] Adapter unit tests (respx)
- Orchestrator
  - [ ] Provider resolution (forced vs greedy)
  - [ ] Per‑provider compile + call + collect
  - [ ] Merge + dedupe + confidence + hashing
  - [ ] Persistence of raw and processed
  - [ ] Instrument timings and counts
- API
  - [ ] POST `/search-runs` handler end‑to‑end
  - [ ] GET `/search-runs/{id}`
  - [ ] Optional: listing endpoint with filters
  - [ ] Error mapping per spec (400/502)
- Observability & security
  - [ ] JSON logging with run_id correlation
  - [ ] Metrics counters/histograms (pluggable)
  - [ ] Bearer auth middleware for POSTs
  - [ ] Scrub sensitive values in logs
- Testing
  - [ ] Unit tests (core, adapters, repos)
  - [ ] Integration tests (happy path, partial/all failures)
  - [ ] E2E tests after each phase and at project end
  - [ ] DB tests with Testcontainers / pytest‑postgresql
  - [ ] Property tests (expansion, merge)
- Packaging & CI
  - [ ] Dockerfile (multi‑stage) and entrypoint
  - [ ] CI workflow (lint, type, test, build, push)
  - [ ] Versioning/tagging scheme
- Deployment
  - [ ] K8s manifests/Helm values (configs, secrets, probes)
  - [ ] Runbook: envs, quotas, SLOs, troubleshooting

---

## 6) Provider Query Mapping Notes

- Common compilation
  - Keywords: `AND`/`OR` join with quotes for multi‑term tokens where needed.
  - Sites: concat `site:domain` terms (joined by OR/space depending on provider limits).
  - Dates: use provider‑specific params; for Brave, prefer freshness param and ignore after/before explicitly per spec.
  - Lang/Geo: map to provider‑specific codes/params (e.g., Google `lr`, `gl`).
- Serper
  - POST JSON with `q`; support `num` for `max_results`; headers with `X-API-KEY`.
- Google CSE
  - GET with `q`, `key`, `cx`, possibly `num`, `lr`, `gl`; quota awareness.
- Brave
  - GET with `q`, `country`, `search_lang`; freshness param; header `X-Subscription-Token`.

---

## 7) Error Semantics & Guardrails

- No fallback to raw user prompt: 502 on LLM call failure.
- 400 on invalid schema or unknown placeholder.
- 502 when all providers fail; partial failures allowed.
- Enforce limits and cap query length; reject early.

---

## 8) Risks & Mitigations

- LLM variability → Temperature 0, strict schema validation, placeholder whitelist.
- Provider quota/latency → Backoff/jitter, timeouts, greedy merge tolerates partial failures.
- Data quality (duplicates, tracking params) → Normalize URLs minimally and hash on canonical form if needed.
- Secrets leakage → Centralized logging filters; avoid logging full headers/keys.
- Performance targets → Async IO, parallel provider calls, warm cache for rewrite.

---

## 9) Milestones & Rough Estimates

- A: Scaffolding, config, healthz — 0.5–1d
- B/C: Domain models, placeholders, limits — 0.5–1d
- D: LLM client + validation + cache — 0.5–1d
- F: DB models + migrations + repos — 1d
- E/G: HTTP infra + 3 adapters — 1–1.5d
- H/I: Orchestrator + API — 1d
- J/K: Observability + security + limits — 0.5d
- L: Tests (unit/integration) — 1–1.5d
- M/N: Docker + CI + deploy scaffolding — 0.5–1d

Total: ~6–9 days elapsed (solo), depending on provider docs and environment.

---

## 10) Open Questions / Assumptions

- Auth scope: Start with internal bearer; mTLS optional later.
- Listing endpoint: Needed day‑1 or later?
- URL normalization: Simple `urlparse` normalization ok, or stricter canonicalization desired?
- Metrics backend: Prometheus preferred? For now, pluggable hooks + logging.
- Postgres connection mgmt: Single pool per process; production sizing TBD.

---

## 11) Next Immediate Steps

1) Scaffold repo and config loading.
2) Implement Pydantic schema + placeholders with tests.
3) Add LLM client (OpenAI) + strict validation pipeline.
4) Define DB models + migrations and repositories.
5) Implement adapters (Serper, Google CSE, Brave) with mocked tests.
6) Build orchestrator, merge/dedupe, and persistence.
7) Wire POST/GET endpoints; add auth, metrics, and logging.
8) Package (Docker), write CI, verify acceptance criteria.

---

This plan is intentionally minimal yet complete to meet the spec’s acceptance criteria and guardrails while leaving room for future providers and orchestration.
