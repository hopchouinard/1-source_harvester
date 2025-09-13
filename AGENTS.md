# Repository Guidelines

## Project Structure & Module Organization
- `app/`: service code (FastAPI, adapters, core, db, llm, observability). Entrypoint: `app/main.py` (`app` ASGI).
- `tests/`: mirrors `app/` by domain (e.g., `tests/core/test_*.py`).
- `configs/`: runtime YAML defaults (`configs/default.yaml`).
- `alembic/`: DB migrations (`alembic.ini`, `alembic/versions`).
- `specs/`: planning docs for phased delivery.

## Build, Test, and Development Commands
- Install: `poetry env use 3.13 && poetry install`.
- Run API (dev): `poetry run uvicorn app.main:app --reload`.
- Tests: `poetry run pytest` (async enabled via `pytest-asyncio`).
- Coverage (optional): `poetry run pytest --cov=app`.
- Lint/format: `poetry run ruff check --fix && poetry run black .`.
- Type-check: `poetry run mypy`.
- Migrate DB: `ALEMBIC_SQLALCHEMY_URL=sqlite:///dev.db poetry run alembic upgrade head`.
 - Pre-commit (optional): `pre-commit install && pre-commit run -a`.

## Coding Style & Naming Conventions
- Python 3.13, 4-space indentation, max line length 100 (Black/Ruff).
- Use type hints everywhere; mypy is strict (`disallow_untyped_defs = true`).
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Imports: first-party package is `app` (Ruff isort config enforces order).

## Testing Guidelines
- Framework: `pytest` + `pytest-asyncio`; HTTP via `httpx.AsyncClient` with `asgi-lifespan`.
- Place tests under `tests/` using `test_*.py`; mirror `app/` structure.
- Mark async tests with `@pytest.mark.asyncio`.
- Use fixtures from `tests/conftest.py` (`app`, `client`).

## Migrations & Database
- Alembic manages schema; initial revision `0001_initial` builds from `app.models.metadata`.
- Local dev: SQLite is fine; set `ALEMBIC_SQLALCHEMY_URL` or `DATABASE_URL`.
- In production, run Alembic migrations rather than `metadata.create_all()`.

## Commit & Pull Request Guidelines
- Commits: imperative, scoped messages (e.g., `feat(core): add orchestrator`); keep changes focused.
 - PRs: include summary, linked issue/spec, test coverage, and local run steps. Add screenshots for API changes when useful (e.g., curl command + JSON response).

## Security & Configuration Tips
- Config: defaults in `configs/default.yaml`. Override via `SH_CONFIG_FILE` or env (e.g., `SH_SEARCH__PROVIDER=google`).
- Secrets via env only: `SH_SERPER_KEY`, `SH_GOOGLE_API_KEY`, `SH_GOOGLE_CSE_ID`, `SH_BRAVE_KEY`, `OPENAI_API_KEY`.
- Prefer `uvicorn` locally; do not log secrets. Validate secrets in `prod` or when `SH_VALIDATE_SECRETS=true`.
