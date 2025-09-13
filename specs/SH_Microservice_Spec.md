# Source Harvester Microservice — End-to-End Spec (v1)

You wanted tight, minimal, and future-proof. Here it is — nothing that smells like “rebuilding Google,” just a clean URL librarian you can ship.

⸻

## 1) Purpose & Scope

Goal: Given a user’s natural-language intent, return a merged, deduped list of URLs from one or more search providers.
Non-goals: No crawling, no parsing, no summarizing, no ranking beyond provider-overlap confidence.
**Trigger: REST call only (stateless). Scheduling/orchestration is a separate service.**

⸻

## 2) Provider-Neutral Query Schema (LLM output)

This is the only thing the mini-model produces. Adapters compile it to provider dialects.

```json
{
"keywords": ["string", "..."],           // REQUIRED
"boolean": "AND|OR",                     // OPTIONAL (default AND)
"filters": {
    "sites": ["example.com", ".eu"],       // OPTIONAL (domains or suffixes)
    "date_after": "{TOKEN}|YYYY-MM-DD",    // OPTIONAL
    "date_before": "{TOKEN}|YYYY-MM-DD",   // OPTIONAL
    "lang": "en|fr|...",                   // OPTIONAL (ISO 639-1)
    "geo": "US|EU|CA|...",                 // OPTIONAL (region bias)
    "max_results": 10                      // OPTIONAL (default 10)
}
}
```

**Allowed date placeholders (fixed whitelist):**
{TODAY} {YESTERDAY} {LAST_WEEK_START} {LAST_WEEK_END} {LAST_MONTH_START} {LAST_MONTH_END}

Validation hard-fails on unknown fields/placeholders.

⸻

## 3) Placeholder System (runtime expansion)

**Expansion (system clock, never LLM):**
 • {TODAY} → YYYY-MM-DD (today)
 • {YESTERDAY} → today − 1d
 • {LAST_WEEK_START} → today − 7d
 • {LAST_WEEK_END} → today
 • {LAST_MONTH_START} → today − 30d
 • {LAST_MONTH_END} → today

**Rules:**
 • LLM may emit placeholders only when the user used relative time.
 • If the user specified explicit dates, LLM emits literal dates (no placeholders).
 • After expansion, no placeholders may remain.

⸻

## 4) REST API

### POST /search-runs

Trigger a run: rewrite → expand placeholders → query providers (greedy) → store results → return processed list.

#### Request

```json
{
  "query": "latest EU AI regulation updates in the last week",
  "options": {
    "lang": "en",
    "maxResults": 10
  }
}
```

#### Response (201)

```json
{
  "run_id": 124,
  "rewritten_template": "(\"AI regulation\" OR \"AI Act\") site:.eu after:{LAST_WEEK_START} before:{LAST_WEEK_END}",
  "final_queries": {
    "serper": "(\"AI regulation\" OR \"AI Act\") site:.eu after:2025-09-05 before:2025-09-12",
    "google": "(\"AI regulation\" OR \"AI Act\") site:.eu after:2025-09-05 before:2025-09-12",
    "brave":  "(\"AI regulation\" OR \"AI Act\") site:.eu"          // brave ignores explicit after/before; adapter uses freshness param
  },
  "providers_used": ["serper","google","brave"],
  "urls": [
    {"url":"https://ec.europa.eu/digital-strategy/news/ai-act-updated.html","providers":["serper","google","brave"],"confidence":3},
    {"url":"https://www.politico.eu/article/eu-ai-act-finalization/","providers":["serper","google"],"confidence":2}
  ],
  "meta": {
    "counts": {"serper": 5, "google": 4, "brave": 3},
    "total_unique": 6
  }
}
```

#### Errors

 • 400 invalid schema/placeholders (LLM returned junk)
 • 502 LLM call failed (timeout/quota/auth)
 • 502 provider call failed (all failed)
 • 500 unexpected

⸻

### GET /search-runs/:id

Return metadata + processed results for a run.

#### Response (200)

```json
{
  "run_id": 124,
  "query": "latest EU AI regulation updates in the last week",
  "rewritten_template": "(\"AI regulation\" OR \"AI Act\") site:.eu after:{LAST_WEEK_START} before:{LAST_WEEK_END}",
  "timestamp": "2025-09-12T14:23:01Z",
  "providers_used": ["serper","google","brave"],
  "urls": [
    {"url":"https://ec.europa.eu/digital-strategy/news/ai-act-updated.html","providers":["serper","google","brave"],"confidence":3},
    {"url":"https://www.politico.eu/article/eu-ai-act-finalization/","providers":["serper","google"],"confidence":2}
  ]
}
```

#### GET /search-runs?query=...&from=...&to=... (optional)

List runs by original query/time range (for dashboards).

⸻

## 5) DB Schema (Postgres)

```sql
-- 1) Cache original -> rewritten template (with placeholders)
CREATE TABLE queries (
  id SERIAL PRIMARY KEY,
  original_query TEXT NOT NULL UNIQUE,
  rewritten_template TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2) Each API-triggered execution
CREATE TABLE search_runs (
  id SERIAL PRIMARY KEY,
  query TEXT NOT NULL,                -- original user text
  rewritten_template TEXT NOT NULL,   -- cached or fresh
  run_timestamp TIMESTAMPTZ DEFAULT now(),
  config JSONB,                       -- provider cascade, options, llm metadata
  providers_used TEXT[] NOT NULL      -- e.g., ["serper","google","brave"]
);

-- 3) Raw per-provider rows (exactly as returned)
CREATE TABLE search_results_raw (
  id SERIAL PRIMARY KEY,
  run_id INT NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,             -- serper|google|brave|...
  url TEXT NOT NULL,
  rank INT,                           -- provider-returned order if available
  meta JSONB,                         -- provider-specific fields (latency, token usage, etc.)
  inserted_at TIMESTAMPTZ DEFAULT now()
);

-- 4) Merged/deduped output for downstream
CREATE TABLE search_results_processed (
  id SERIAL PRIMARY KEY,
  run_id INT NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  providers TEXT[] NOT NULL,          -- who found it
  confidence INT NOT NULL,            -- COUNT(DISTINCT provider)
  dedupe_hash TEXT NOT NULL,          -- e.g., SHA1(url)
  inserted_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_processed_run_hash ON search_results_processed(run_id, dedupe_hash);
CREATE INDEX idx_raw_run_provider ON search_results_raw(run_id, provider);
```

Contract: Downstream fetchers only read from search_results_processed.

⸻

## 6) Config Model (YAML)

```yaml
search:
  provider: "auto"              # auto | serper | google | brave | ...
  cascade_order: ["serper","google","brave"]
  default_options:
    maxResults: 10
    lang: "en"

llm:
  provider: "openai"            # openai | anthropic | gemini | local
  model: "gpt-4.1-mini"         # swap at will
  api_key_env: "OPENAI_API_KEY"
  endpoint: "<https://api.openai.com/v1/chat/completions>"
  temperature: 0.0
  max_tokens: 512
  prompt_file: "prompts/rewrite_query.txt"
```

 • **Model & prompt are config-driven. Change without code changes.**
 • **provider: auto + greedy behavior: hit all in cascade_order, merge, dedupe.**

⸻

## 7) LLM Prompt (file)

### prompts/rewrite_query.txt

```text
You rewrite user intent into a provider-neutral JSON search schema.

Rules:

- Output ONLY valid JSON with fields: keywords[], boolean ("AND"|"OR"), filters {sites[], date_after, date_before, lang, geo, max_results}.
- If the user used relative dates, use ONLY these placeholders: {TODAY} {YESTERDAY} {LAST_WEEK_START} {LAST_WEEK_END} {LAST_MONTH_START} {LAST_MONTH_END}.
- If the user provided explicit dates, emit YYYY-MM-DD literals.
- Do not invent new fields or placeholders. No markdown, no commentary.
```

⸻

## 8) Validation & Expansion

**Schema validation (pre-DB):**
 • keywords: non-empty array of strings
 • boolean: enum AND|OR (default AND)
 • filters: object with only known keys
 • date_*: either ISO date or allowed placeholder
 • Reject unknown placeholders or stray {}

**Expansion (at run time):**
 • Expand placeholders using system clock
 • Hard-fail if any placeholder remains

Why strict? Predictability. If the model gets “creative,” you catch it here — not in production.

⸻

## 9) Provider Adapters (normalization contract)

### Interface

```typescript
interface SearchProviderAdapter {
  name: string; // "serper" | "google" | "brave" | ...
  search(schema: ProviderNeutralQuery, options?: SearchOptions): Promise<SearchResult>;
}
interface SearchResult {
  provider: string;
  queryUsed: string;     // provider-compiled query string or params
  urls: string[];
  meta?: any;            // latency, credits, raw response (optional)
}
```

**Greedy orchestrator**
 • Resolve forced provider vs auto
 • For each provider in cascade_order: build provider query from schema → call → collect
 • Merge results: providers set per URL, confidence = count(providers)
 • Store raw & processed
 • Return processed list

⸻

## 10) Error Semantics (no silent fallbacks)

### • LLM failure → 502 Bad Gateway

```json
{"error":"LLM call failed","details":"timeout after 5s"}
```

### • Invalid LLM output → 400 Bad Request

```json
{"error":"invalid schema","details":"unknown placeholder {PAST_2_WEEKS}"}
```

### • All providers failed → 502 Bad Gateway

```json
{"error":"providers failed","details":"serper:403; google:quota; brave:timeout"}
```

### • Partial provider failure is fine (greedy): you still return merged results from those that worked.

Retry policy: external orchestrator’s job, not this service.

⸻

## 11) Security, Observability, Ops

 • **Auth:** at minimum, bearer token or mTLS for internal calls.
 • **Secrets:** API keys only via env vars (*_API_KEY).
 • **Logging:** run_id, provider timings, counts, errors, queryUsed per provider (debug).
 • **Metrics:**
     • per-provider latency, success rate, URLs returned
     • overlap distribution (confidence histogram)
     • error rates by reason (LLM vs provider)
 • **Limits:** final query length cap (e.g., 512 chars), max keywords (e.g., 12), max sites (e.g., 20).
 • **Idempotency:** same query reuses cached rewritten_template from queries. Placeholders ensure freshness remains dynamic.

⸻

## 12) Acceptance Criteria (ship-ready)

 • POST /search-runs with a valid query returns 201 and a processed list within P95 < 3s (cold) / < 1.5s (warm cache).
 • DB gets exactly one search_runs row, N search_results_raw rows, and K search_results_processed rows (K ≤ sum of N).
 • Confidence equals number of distinct providers that surfaced each URL.
 • If LLM outputs an unsupported placeholder, request fails with 400 (no provider calls made).
 • If all providers error, request fails with 502.
 • Downstream fetchers can rely solely on search_results_processed keyed by run_id.

⸻

## 13) Minimal Sequence (happy path)

```text
Client → POST /search-runs {query, options}
Service:

  1) lookup queries.original_query
     - hit → use rewritten_template
     - miss → call LLM → validate → store
  2) expand placeholders → provider-neutral schema → per-provider query build
  3) call providers (greedy) → collect raw
  4) merge & dedupe → providers[], confidence
  5) insert search_runs, raw, processed
  6) return processed payload (201)
```

⸻

## 14) Source Harvester Microservice — Tech Stack (Definitive)

### Runtime & Language

- Python 3.12(async-first, great ecosystem, mirrors retriever)

### Web Framework

- FastAPI 0.115+ (async; OpenAPI + Pydantic v2)
- Uvicorn (ASGI) behind gunicorn (uvicorn.workers.UvicornWorker)

### HTTP & Provider Connectivity

- httpx 0.27+ (async client, retries, timeouts)
- Provider adapters (pluggable modules):
  - Serper: POST <https://google.serper.dev/search>
  - Google Custom Search JSON API: GET <https://www.googleapis.com/customsearch/v1>
  - Brave Search API: GET <https://api.search.brave.com/res/v1/web/search>
- Backoff & jitter for provider HTTP 429/5xx
- Per-provider request metrics (latency, status, URLs returned)

### LLM (Prompt Rewriter → Provider-Neutral Schema)

- Config-driven client for OpenAI / Anthropic / Google (swap by config)
- Temperature 0.0, max_tokens ≤ 512
- Prompt file on disk (hot-swappable; hashed for auditing)
- Strict JSON validation (Pydantic) + placeholder whitelist validator

### Placeholder Expansion (runtime)

- Fixed tokens only: {TODAY}, {YESTERDAY}, {LAST_WEEK_START}, {LAST_WEEK_END}, {LAST_MONTH_START}, {LAST_MONTH_END}
- Expansion via Python datetime, never via LLM
- Hard-fail if unknown/leftover placeholders

### Provider-Neutral Schema (what LLM returns)

```json
{
  "keywords": ["..."],              // required
  "boolean": "AND|OR",              // optional
  "filters": {
    "sites": ["example.com",".eu"], // optional
    "date_after": "{TOKEN}|YYYY-MM-DD",
    "date_before": "{TOKEN}|YYYY-MM-DD",
    "lang": "en|fr",
    "geo": "US|EU|CA",
    "max_results": 10
  }
}
```

Adapters compile this to provider-specific queries/params.

### Data & Persistence (PostgreSQL 15+)

- SQLAlchemy 2.0 (Core or ORM) + asyncpg
- Alembic migrations
- Tables (from spec):
  - queries (cache original → rewritten_template)
  - search_runs (each POST execution)
  - search_results_raw (per-provider URLs + rank, meta)
  - search_results_processed (merged, deduped; providers[], confidence, dedupe_hash)
- Unique indexes:
  - (run_id, dedupe_hash) on processed
  - original_query on queries

### Config

- pydantic-settings for env/.env
- YAML app config:
  - search.provider: auto|serper|google|brave
  - search.cascade_order: [serper, google, brave]
  - search.default_options: { maxResults: 10, lang: "en" }
  - llm.* (provider/model/endpoint/prompt_file/temp/max_tokens)
- Provider API keys via env vars:
  - SERPER_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, BRAVE_KEY, OPENAI_API_KEY, etc.

### Orchestration Model

- Greedy mode by default: hit all providers in cascade_order, merge, dedupe
- Config override: provider != "auto" forces a single provider
- Merge policy:
  - union of all URLs
  - providers = set of sources that returned each URL
  - confidence = count of providers per URL
  - store raw and processed snapshots per run

### Observability

- structlog or loguru for JSON logs (include run_id, provider, latency)
- /healthz endpoint: DB ping + outbound DNS/HTTP probe

### Testing

- pytest + pytest-asyncio
- respx (HTTP mocking for httpx)
- LLM layer: mock client returning fixed JSON
- DB: pytest-postgresql or Testcontainers
- Property tests for:
  - placeholder expansion
  - schema validation
  - greedy merge/dedupe/consensus

### Packaging & CI/CD

- Poetry or uv for deps
- ruff + black + pyright (or mypy)
- SemVer image tags: source-harvester:<version>

### Deployment

- Docker (multi-stage, slim)
- Config via ConfigMaps/Secrets
- Readiness probe hits /healthz
- Ingress via NGINX/Envoy
- Sentry (optional) for exception tracking

### Security

- Internal JWT/Bearer or mTLS required for POSTs
- Secrets from K8s Secrets / cloud secret manager
- No background crawling; only acts when called
- Provider quotas respected; backoff on 429
- Logs scrub query text if it may include PII (configurable)

### Performance & Limits

- LLM timeout: 5s (fail hard with 502)
- Provider timeout: 3–4s each; total run target < 2–3s p95 (cache warm)
- Final query length cap: 512 chars
- Keywords cap: 12; sites cap: 20 (configurable)
- Idempotency:
  - Same original_query → reuse rewritten_template from queries
  - Placeholders ensure freshness remains relative to “now”

### Example Dockerfile

```dockerfile
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && poetry install --no-dev
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-w","2","-b","0.0.0.0:8080","app.main:app"]
```

### Service Ports & Resources

- HTTP port: 8080

### Minimal Module Layout

```text
app/
  main.py                 # FastAPI app, routes (/search-runs, /search-runs/:id)
  config.py               # pydantic-settings + YAML loader
  models.py               # SQLAlchemy tables
  adapters/
    base.py               # SearchProviderAdapter interface
    serper.py             # Serper adapter
    google.py             # Google CSE adapter
    brave.py              # Brave adapter
  llm/
    client.py             # provider-agnostic LLM client
    prompts/              # rewrite_query.txt (mounted from config path)
  core/
    schema.py             # Provider-neutral schema (Pydantic)
    placeholders.py       # whitelist + expansion
    orchestrator.py       # greedy/forced orchestration, merge/dedupe, confidence
    validation.py         # strict JSON + placeholder validation
    hashing.py            # URL dedupe hash
  db/
    session.py            # async session helpers
    queries.py            # cache lookup/insert, run inserts
  observability/
    metrics.py, logging.py
```

### OpenAPI (FastAPI auto)

- POST /search-runs → 201, or 400/502 on schema/LLM/provider failures
- GET /search-runs/{id}
- (Optional) GET /search-runs?query=...&from=...&to=...

### Guardrails (non-negotiable)

- No fallback to raw user prompt. If LLM fails → hard stop (502).
- Strict schema & placeholder validation (400 on violation).
- Greedy merge returns union of URLs with providers[] and confidence.
- Raw + processed are both persisted per run (snapshots; immutable).

⸻
