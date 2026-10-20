.PHONY: help install install-web lint lint-fix format format-check type-check test test-unit test-integration validate up down clean

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff
MYPY   := .venv/bin/mypy

help:
	@echo "AgentOps Development Makefile"
	@echo "============================="
	@echo "install          - Install backend dependencies in .venv"
	@echo "install-web      - Install frontend dependencies in apps/web"
	@echo "lint             - Run Ruff linting check on backend code"
	@echo "lint-fix         - Auto-fix linting issues where supported"
	@echo "format           - Auto-format backend code using Ruff"
	@echo "format-check     - Verify backend code formatting"
	@echo "type-check       - Run static type checking using mypy"
	@echo "test             - Run all backend tests"
	@echo "test-unit        - Run unit tests only"
	@echo "test-integration - Run integration tests only"
	@echo "validate         - Run full quality gate (lint, format, type-check, test)"
	@echo "up               - Start Docker Compose services (project: agentops)"
	@echo "down             - Stop Docker Compose services (project: agentops)"
	@echo "clean            - Remove Python cache files, test caches, and coverage"

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

install-web:
	npm --prefix apps/web install

lint:
	$(RUFF) check .

lint-fix:
	$(RUFF) check --fix .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

type-check:
	$(MYPY) services/backend/app

test:
	$(PYTEST) services/backend/tests

test-unit:
	$(PYTEST) services/backend/tests/unit

test-integration:
	$(PYTEST) services/backend/tests/integration

validate: lint format-check type-check test
	@echo "==> All quality gate checks PASSED cleanly."

up:
	docker compose -p agentops up -d

down:
	docker compose -p agentops down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov 2>/dev/null || true
