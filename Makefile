# Default variables
PY?=poetry
PORT?=8000
DB_URL?=sqlite:///dev.db

.PHONY: help install run test coverage lint format typecheck migrate precommit-install precommit
.DEFAULT_GOAL := help

help: ## Show this help.
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-20s %s\n", $$1, $$2}'

install: ## Set Python 3.13 and install deps via Poetry
	$(PY) env use 3.13
	$(PY) install --with dev

run: ## Run the API locally with reload (uvicorn)
	$(PY) run uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

test: ## Run tests (pytest)
	$(PY) run pytest

coverage: ## Run tests with coverage report
	$(PY) run pytest --cov=app

lint: ## Lint the code (Ruff) without fixing
	$(PY) run ruff check .

format: ## Auto-fix lint issues and format code (Ruff + Black)
	$(PY) run ruff check --fix .
	$(PY) run black .

typecheck: ## Type-check with mypy
	$(PY) run mypy

migrate: ## Apply DB migrations to head (set DB_URL or use default SQLite)
	ALEMBIC_SQLALCHEMY_URL=$(DB_URL) $(PY) run alembic upgrade head

precommit-install: ## Install pre-commit hooks (requires pre-commit in env)
	$(PY) run pre-commit install

precommit: ## Run all pre-commit hooks against all files (optional)
	$(PY) run pre-commit run -a

