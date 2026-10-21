.PHONY: help install install-web lint lint-fix format format-check type-check test test-unit test-integration test-contract test-evals test-frontend validate validate-all validate-n8n scan-secrets audit worker up down clean

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
	@echo "test-evals       - Run deterministic agent evaluation suite"
	@echo "test-frontend    - Run frontend unit and component tests"
	@echo "validate         - Run core quality gate (lint, format, type-check, test)"
	@echo "validate-all     - Run full 11-step CI verification locally"
	@echo "validate-n8n     - Validate n8n workflow JSON files"
	@echo "scan-secrets     - Scan repository for accidental secret leakage"
	@echo "audit            - Run license and dependency vulnerability audit"
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
	npm --prefix apps/web run format:check

type-check:
	$(MYPY) services/backend/app services/backend/tests

test:
	$(PYTEST) services/backend/tests

test-unit:
	$(PYTEST) services/backend/tests/unit

test-integration:
	$(PYTEST) services/backend/tests/integration

test-contract:
	$(PYTEST) -m contract -v

test-evals:
	$(PYTEST) services/backend/tests/evals -v

test-frontend:
	npm --prefix apps/web test

validate-n8n:
	$(PYTHON) scripts/validate_n8n_workflows.py

scan-secrets:
	$(PYTHON) scripts/scan_secrets.py

audit:
	$(PYTHON) scripts/audit_dependencies.py

validate: lint format-check type-check test
	@echo "==> All core quality gate checks PASSED cleanly."

validate-all: lint format-check type-check test validate-n8n scan-secrets audit test-frontend
	docker compose -p agentops config > /dev/null
	docker compose -p agentops --profile ollama config > /dev/null
	@echo "==> All 11 CI verification checks PASSED cleanly."

worker:
	PYTHONPATH=services/backend $(PYTHON) -m celery -A app.workers.celery_app worker --loglevel=info --pool=threads --concurrency=4 -Q agentops.runs


up:
	docker compose -p agentops up -d

down:
	docker compose -p agentops down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov 2>/dev/null || true
