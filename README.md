# Source Harvester Microservice

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

This repository is being implemented phase-by-phase per the plan. Current status: Phase A — Scaffolding.

Configuration (Phase B)
- YAML: `configs/default.yaml` is loaded by default. Override via `SH_CONFIG_FILE=/path/to/config.yaml`.
- Env overrides: use nested variables, e.g. `SH_SEARCH__PROVIDER=google`, `SH_LLM__PROVIDER=openai`.
- Secrets (env only):
  - Providers: `SH_SERPER_KEY`, `SH_GOOGLE_API_KEY`, `SH_GOOGLE_CSE_ID`, `SH_BRAVE_KEY`
  - LLM: `OPENAI_API_KEY` (or `SH_OPENAI_API_KEY`)
- Secret enforcement: enforced in `prod` or when `SH_VALIDATE_SECRETS=true`.
