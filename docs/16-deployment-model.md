# Deployment Model & Infrastructure: AgentOps

## 1. Local-First Containerized Topology

AgentOps is designed for local-first deployment using Docker Compose. All components communicate over an isolated internal bridge network (`agentops-net`). Only necessary ports are published, and all host bindings default to loopback (`127.0.0.1`).

```mermaid
flowchart TD
    subgraph Host["Host Machine"]
        UserBrowser["Web Browser (127.0.0.1:3000)"]
        UserAPI["API Client (127.0.0.1:8000)"]
    end

    subgraph DockerCompose["Docker Compose (agentops-net)"]
        Frontend["frontend (Next.js)"]
        BackendAPI["backend-api (FastAPI)"]
        BackendWorker["backend-worker (Celery + LangGraph)"]
        N8N["n8n (Community Automation)"]
        Postgres[("postgres:16-alpine")]
        Redis[("redis:7.2-alpine")]

        PostgresVol[("postgres_data")]
        RedisVol[("redis_data")]
        N8NVol[("n8n_data")]
    end

    UserBrowser -->|127.0.0.1:3000| Frontend
    UserAPI -->|127.0.0.1:8000| BackendAPI

    Frontend --> BackendAPI
    BackendAPI --> Postgres
    BackendAPI --> Redis
    BackendWorker --> Redis
    BackendWorker --> Postgres
    BackendAPI -.-> N8N

    Postgres --- PostgresVol
    Redis --- RedisVol
    N8N --- N8NVol
```

---

## 2. Docker Compose Specification

### 2.1 Compose Service Manifest

```yaml
version: "3.8"

networks:
  agentops-net:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  n8n_data:

services:
  postgres:
    image: postgres:16-alpine
    container_name: agentops-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-agentops_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agentops_pass}
      POSTGRES_DB: ${POSTGRES_DB:-agentops_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    networks:
      - agentops-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agentops_user -d agentops_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-alpine
    container_name: agentops-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    networks:
      - agentops-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend-api:
    build:
      context: .
      dockerfile: docker/backend.Dockerfile
    container_name: agentops-api
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://agentops_user:agentops_pass@postgres:5432/agentops_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    ports:
      - "127.0.0.1:8000:8000"
    networks:
      - agentops-net
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  backend-worker:
    build:
      context: .
      dockerfile: docker/backend.Dockerfile
    container_name: agentops-worker
    restart: unless-stopped
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://agentops_user:agentops_pass@postgres:5432/agentops_db
      - SYNC_DATABASE_URL=postgresql://agentops_user:agentops_pass@postgres:5432/agentops_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    networks:
      - agentops-net
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  n8n:
    image: n8nio/n8n:latest
    container_name: agentops-n8n
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=agentops_admin_pass
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - agentops-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: agentops-frontend
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
    networks:
      - agentops-net
    depends_on:
      - backend-api
```

---

## 3. Container Security Hardening

- **Non-Root Execution**: Dockerfiles create dedicated unprivileged users (`appuser` with UID/GID 10001) and execute the runtime under that user.
- **Minimal Base Images**: Multi-stage builds based on `python:3.10-slim` and `node:20-alpine` minimize package surface area.
- **Zero Exposed Sockets to Public**: Database and message broker ports are bound exclusively to `127.0.0.1` on the host, preventing remote network connections.

---

## 4. Continuous Integration Pipeline (GitHub Actions)

The repository CI workflow (`.github/workflows/ci.yml`) executes on every push and pull request to `main`:

```yaml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run Ruff Linter & Formatter
        run: |
          ruff check .
          ruff format --check .

      - name: Run Security Audit (Bandit)
        run: |
          pip install bandit
          bandit -r backend/app -ll

      - name: Run Pytest Suite
        run: |
          pytest backend/tests --strict-markers
```
