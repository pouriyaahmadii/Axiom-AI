# AGENTS.md - AgentOps Workspace Rules

## 1. Scope and Boundary
- Project Name: AgentOps
- Compose Namespace: COMPOSE_PROJECT_NAME=agentops
- Workspace Root: Strictly execute inside `./`. Never inspect or modify parent `../` paths.
- Tech Stack: Python 3.12 (FastAPI, LangGraph, Celery), Next.js 14, PostgreSQL, Redis, Docker Compose.

## 2. Port & Resource Isolation
- Frontend: Bind strictly to port `3000`.
- Backend FastAPI: Bind strictly to port `8000`.
- PostgreSQL: Host port `5432`. Container name prefix: `agentops_postgres`.
- Redis: Host port `6379`. Container name prefix: `agentops_redis`.
- n8n: Host port `5678`. Container name prefix: `agentops_n8n`.
- Forbidden Ports: Do not bind or kill processes on ports `8080`, `6333`, `5433`, `6380`.

## 3. Shell & Execution Safety
- Never run global cleanup commands like `docker system prune -a` or `killall`.
- Only terminate processes by specific PID associated with this workspace.
- Always use explicit project flags for Docker: `docker compose -p agentops <command>`.
- Python commands must strictly use `./.venv/bin/activate` or `poetry run`.