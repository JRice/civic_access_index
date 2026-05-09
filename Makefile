.PHONY: help install lint test run-api run-worker run-scheduler db-up migrate seed compose-up compose-down

help:
	@echo "Civic Access Index development commands"
	@echo "  make install       Install Python dependencies with uv"
	@echo "  make lint          Run ruff checks"
	@echo "  make test          Run tests"
	@echo "  make run-api       Run FastAPI locally"
	@echo "  make run-worker    Run Celery worker locally"
	@echo "  make compose-up    Start local Docker stack"

install:
	uv sync --all-extras --dev

lint:
	uv run ruff check app tests scripts

test:
	uv run pytest

run-api:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	uv run celery -A app.workers.celery_app worker --loglevel=INFO

run-scheduler:
	uv run celery -A app.workers.celery_app beat --loglevel=INFO

db-up:
	docker compose up -d postgres redis

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/load_local_seed_data.py

compose-up:
	docker compose up --build

compose-down:
	docker compose down

