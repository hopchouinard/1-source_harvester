SHELL := /bin/bash

# Variables
PYTHON ?= python3
POETRY ?= poetry
PORT ?= 8000
DB_URL ?= sqlite:///dev.sqlite3

# Docker
IMAGE ?= source-harvester:local
REGISTRY ?= ghcr.io
IMAGE_NAME ?= source-harvester

.PHONY: install run test coverage lint format typecheck migrate docker-build docker-run docker-push docker-health compose-up compose-down compose-logs

install:
	$(POETRY) env use 3.13
	$(POETRY) install

run:
	$(POETRY) run uvicorn app.main:app --reload --port $(PORT)

test:
	$(POETRY) run pytest -q

coverage:
	$(POETRY) run pytest --cov=app --cov-report=term-missing

lint:
	$(POETRY) run ruff check .

format:
	$(POETRY) run ruff check . --fix
	$(POETRY) run black .

typecheck:
	$(POETRY) run mypy

migrate:
	ALEMBIC_SQLALCHEMY_URL=$(DB_URL) $(POETRY) run alembic upgrade head

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker run --rm -p $(PORT):8000 -e SH_ENVIRONMENT=dev $(IMAGE)

docker-push:
	@if [[ -z "$(TAG)" ]]; then echo "Set TAG=<version> to push"; exit 1; fi
	docker tag $(IMAGE) $(REGISTRY)/$(IMAGE_NAME):$(TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(TAG)

docker-health:
	curl -sf http://localhost:$(PORT)/healthz | jq .

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v

compose-logs:
	docker compose logs -f app
