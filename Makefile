.PHONY: help install lint format test test-unit test-integration up down clean

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff

help:
	@echo "AgentOps Development Makefile"
	@echo "-----------------------------"
	@echo "install          - Install backend dependencies"
	@echo "lint             - Run linter and formatting checks"
	@echo "format           - Auto-format code using ruff"
	@echo "test             - Run all backend tests"
	@echo "test-unit        - Run unit tests only"
	@echo "test-integration - Run integration tests only"
	@echo "up               - Start Docker Compose services"
	@echo "down             - Stop Docker Compose services"
	@echo "clean            - Remove Python cache files and artifacts"

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

test:
	$(PYTEST) services/backend/tests

test-unit:
	$(PYTEST) services/backend/tests/unit

test-integration:
	$(PYTEST) services/backend/tests/integration

up:
	docker compose up -d

down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
