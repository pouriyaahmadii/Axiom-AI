#!/usr/bin/env bash
set -euo pipefail

echo "==> Starting AgentOps development services via Docker Compose..."
docker compose -p agentops up -d postgres redis

echo "==> Waiting for PostgreSQL and Redis readiness..."
docker compose -p agentops exec postgres pg_isready -U agentops_user -d agentops_db || true

echo "==> Starting FastAPI backend on http://127.0.0.1:8000..."
uvicorn app.main:app --app-dir services/backend --host 127.0.0.1 --port 8000 --reload
