# Local Infrastructure Runbook (`docs/runbooks/local-infrastructure.md`)

This runbook documents the architecture, lifecycle management, security controls, and operational procedures for the local AgentOps infrastructure and application services managed via Docker Compose (Phase 22).

---

## 1. Architecture & Service Topology

AgentOps utilizes Docker Compose to establish an isolated, local-first runtime environment consisting of 6 core cooperating services and an optional local model container:

```
+─────────────────────────────────────────────────────────────────────────────────────────+
| Host Machine (Developer Workstation)                                                    |
|                                                                                         |
|  [ Web Browser ] ──────> http://127.0.0.1:3000 (Next.js Dashboard)                      |
|  [ API Client ]  ──────> http://127.0.0.1:8000 (FastAPI Swagger & Endpoints)            |
|  [ n8n UI ]      ──────> http://127.0.0.1:5678 (n8n Workflow Editor)                    |
|                                                                                         |
|  [ Ollama Daemon ] ────> http://127.0.0.1:11434 (Optional Host-Native Model Engine)     |
|  [ Local Python Host ] ─(via compose.override.yaml)─> 127.0.0.1:5432 / 6379             |
+────────────────────────────────────────────┬────────────────────────────────────────────+
                                             │ Loopback Only (127.0.0.1)
                                             ▼
+─────────────────────────────────────────────────────────────────────────────────────────+
| Docker Network: `agentops-net` (Bridge, Isolated)                                       |
|                                                                                         |
|   +────────────────────────+                +─────────────────────────+                 |
|   | Container:             |   HTTP:8000    | Container:              |                 |
|   | `agentops_frontend`    |───────────────>| `agentops_api`          |                 |
|   | Image: frontend:latest | (proxy/ingress)| Image: backend:latest   |                 |
|   | User: nextjs (1001)    |                | User: appuser (10001)   |                 |
|   +────────────────────────+                +────────────┬────────────+                 |
|                                                          │                              |
|   +────────────────────────+                             │ Celery & Postgres            |
|   | Container:             |                             │                              |
|   | `agentops_worker`      |<────────────────────────────┤                              |
|   | Image: backend:latest  |                             │                              |
|   | User: appuser (10001)  |                             ▼                              |
|   +───────────┬────────────+                +─────────────────────────+                 |
|               │                             | Container:              |                 |
|               │                             | `agentops_postgres`     |                 |
|               │ Redis & Tasks               | Image: postgres:16.4    |                 |
|               │                             | DBs: agentops_db, n8n_db|                 |
|               ▼                             +────────────┬────────────+                 |
|   +────────────────────────+                             │                              |
|   | Container:             |                             │ SQL:5432                     |
|   | `agentops_redis`       |                             ▼                              |
|   | Image: redis:7.2.6     |                +─────────────────────────+                 |
|   +────────────────────────+                | Container:              |                 |
|                                             | `agentops_n8n`          |                 |
|                                             | Image: n8n:1.70.0       |                 |
|                                             | User: node (1000)       |                 |
|                                             +─────────────────────────+                 |
|   +────────────────────────+                                                            |
|   | (Optional)             |                                                            |
|   | `agentops_ollama`      | (Profile: 'ollama')                                        |
|   | Image: ollama:0.4.4    |                                                            |
|   +────────────────────────+                                                            |
+─────────────────────────────────────────────────────────────────────────────────────────+
```

### Complete Service Specifications

| Service | Container Name | Image Specification | Default Host Port | Internal Port | Memory Limit | CPU Limit | Persistence Volume |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | `agentops_postgres` | `postgres:16.4-alpine` | *Unpublished* | `5432` | 512 MB | 1.0 CPU | `postgres_data:/var/lib/postgresql/data` |
| **Redis** | `agentops_redis` | `redis:7.2.6-alpine` | *Unpublished* | `6379` | 256 MB | 0.5 CPU | `redis_data:/data` |
| **Backend API** | `agentops_api` | `agentops-backend:latest` (built) | `127.0.0.1:8000` | `8000` | 512 MB | 1.0 CPU | *None (Stateless)* |
| **Backend Worker** | `agentops_worker` | `agentops-backend:latest` (reused)| *Unpublished* | *None* | 768 MB | 1.5 CPU | *None (Stateless)* |
| **Frontend** | `agentops_frontend` | `agentops-frontend:latest` (built)| `127.0.0.1:3000` | `3000` | 512 MB | 1.0 CPU | *None (Stateless)* |
| **n8n Community** | `agentops_n8n` | `n8nio/n8n:1.70.0` | `127.0.0.1:5678` | `5678` | 512 MB | 1.0 CPU | `n8n_data:/home/node/.n8n` |
| *(Optional) Ollama* | `agentops_ollama` | `ollama/ollama:0.4.4` (profile) | `127.0.0.1:11434`| `11434`| 4096 MB | 4.0 CPU | `ollama_data:/root/.ollama` |

---

## 2. Security & Port Isolation Principles

### 1. Loopback-Only Host Bindings
- All published container ports strictly bind to `127.0.0.1` (`127.0.0.1:8000:8000`, `127.0.0.1:3000:3000`, `127.0.0.1:5678:5678`).
- **Zero Public Exposure**: Containers are never bound to `0.0.0.0` or public interface adapters, preventing unintended intranet or internet exposure.

### 2. Unpublished Databases by Default
- In `compose.yaml`, PostgreSQL (`5432`) and Redis (`6379`) specify `expose` only and do not publish host ports.
- Containers on `agentops-net` reach them via internal DNS names (`postgres:5432`, `redis:6379`).

### 3. Optional Host Port Publishing (`compose.override.yaml`)
For local host development (e.g. running pytest or Alembic on the host against containerized PostgreSQL/Redis):
```bash
cp compose.override.yaml.example compose.override.yaml
docker compose -p agentops up -d
```
Docker Compose automatically merges `compose.override.yaml` (ignored by `.gitignore`) and binds `127.0.0.1:5432` and `127.0.0.1:6379`.

### 4. Forbidden Workspace Ports
Per workspace isolation rules (`AGENTS.md`), the following ports are reserved for sibling workspaces and are strictly forbidden:
- `8080`, `5433`, `6380`, `6333`.

### 5. Unprivileged Non-Root Containers
- `agentops_api` & `agentops_worker`: Run as dedicated unprivileged user `appuser` (UID `10001`, GID `10001`).
- `agentops_frontend`: Runs as dedicated unprivileged user `nextjs` (UID `1001`, GID `1001`).
- `agentops_n8n`: Runs as unprivileged user `node` (UID `1000`, GID `1000`).

---

## 3. Image Strategy & Entrypoints

### Backend Image Reuse
Both `backend-api` and `backend-worker` share the identical multi-stage Dockerfile (`infra/docker/backend.Dockerfile`) and image tag (`agentops-backend:latest`). This avoids building two separate Python images and guarantees identical runtime dependency versions.

Service differentiation is achieved through explicit service-specific commands:
- **`backend-api`**:
  ```bash
  sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
  ```
  Automatically applies any pending schema migrations to `agentops_db` before binding the Uvicorn ASGI server.
- **`backend-worker`**:
  ```bash
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
  ```
  Consumes asynchronous tasks from Redis queue `1` and writes results to queue `2`.

### Frontend Standalone Build
`infra/docker/frontend.Dockerfile` utilizes Next.js 14 Standalone output (`output: 'standalone'` in `apps/web/next.config.mjs`). The runner stage copies only `.next/standalone`, `.next/static`, and `public`, producing a lean, production-optimized container running with Node.js without requiring full development `node_modules`.

---

## 4. Healthchecks & Startup Dependency Graph

Services enforce strict readiness dependencies via Docker Compose `condition: service_healthy`:

```
                 ┌──────────────┐          ┌──────────────┐
                 │   postgres   │          │    redis     │
                 └──────┬───────┘          └──────┬───────┘
                        │ (healthy)               │ (healthy)
                        ├─────────────────────────┤
                        │                         │
                        ▼                         │
               ┌────────────────┐                 │
               │  backend-api   │                 │
               └────────┬───────┘                 │
                        │ (healthy)               │
          ┌─────────────┴─────────────┐           │
          ▼                           ▼           │
┌──────────────────┐        ┌──────────────────┐  │
│     frontend     │        │  backend-worker  │◄─┘
└──────────────────┘        └──────────────────┘
```

1. **`postgres` Healthcheck**:
   `pg_isready -U postgres_admin -d postgres` (5s interval, 5 retries).
2. **`redis` Healthcheck**:
   `redis-cli ping` (5s interval, 5 retries).
3. **`backend-api` Healthcheck**:
   `curl -fsS http://127.0.0.1:8000/health/ready || exit 1` (probes database and cache connectivity).
4. **`backend-worker` Healthcheck**:
   `python -c "import redis; r = redis.Redis.from_url('redis://redis:6379/1'); r.ping()"` (15s interval).
5. **`frontend` Healthcheck**:
   `wget --no-verbose --tries=1 --spider http://127.0.0.1:3000 || exit 1` (10s interval).
6. **`n8n` Healthcheck**:
   `wget --no-verbose --tries=1 --spider http://127.0.0.1:5678/healthz || exit 1` (10s interval).

---

## 5. Model Providers: Deterministic Demo vs. External Real Providers

### Deterministic Demo Mode (Zero Paid APIs)
By default, AgentOps is configured for deterministic local evaluation without paid API keys:
- `LLM_PROVIDER=mock`
- `SEARCH_PROVIDER=mock`
- `MOCK_DETERMINISTIC_SEED=42`

In this mode, all 6 services execute end-to-end research runs, DAG planning, tool sandboxes, evidence collection, and report generation 100% offline.

### Optional Ollama Integration
1. **Host-Native Ollama (Default)**:
   Containers map `host.docker.internal:host-gateway`. When running Ollama on your host workstation, point `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
2. **Containerized Ollama Profile**:
   To run Ollama inside Docker Compose:
   ```bash
   docker compose -p agentops --profile ollama up -d
   ```

### No Silent Fallback Guarantee
If a user requests `LLM_PROVIDER=openai` without configuring `OPENAI_API_KEY`:
- The provider factory raises an explicit `AuthenticationError`.
- The system **never silently falls back to Mock mode** when a real provider was requested.
- Every run and audit event clearly records the chosen provider (`mock`, `openai`, or `ollama`).

---

## 6. Operational Commands & Lifecycle

All operations use the explicit project identifier `-p agentops`.

### Bootstrap Environment Configuration
```bash
# 1. Create local .env from example template
cp .env.example .env

# 2. Verify Docker Compose configuration
docker compose -p agentops config
```

### Starting the Full Stack
```bash
# Build and start all 6 cooperating services
docker compose -p agentops up -d --build
```

### Inspecting Service Health
```bash
docker compose -p agentops ps
```
Expected output:
```
NAME                IMAGE                     COMMAND                  SERVICE          STATUS
agentops_api        agentops-backend:latest   "sh -c 'alembic upgr…"   backend-api      Up (healthy)
agentops_frontend   agentops-frontend:latest  "node server.js"         frontend         Up (healthy)
agentops_n8n        n8nio/n8n:1.70.0          "tini -- /docker-ent…"   n8n              Up (healthy)
agentops_postgres   postgres:16.4-alpine      "docker-entrypoint.s…"   postgres         Up (healthy)
agentops_redis      redis:7.2.6-alpine        "docker-entrypoint.s…"   redis            Up (healthy)
agentops_worker     agentops-backend:latest   "celery -A app.worke…"   backend-worker   Up (healthy)
```

### Graceful Shutdown (Non-Destructive)
```bash
# Stop containers without removing networks or volumes
docker compose -p agentops stop

# Or stop and remove containers while preserving persistent volumes
docker compose -p agentops down
```
> [!IMPORTANT]
> `docker compose down` retains named volumes (`postgres_data`, `redis_data`, `n8n_data`). Database tables and n8n credentials remain completely intact across restarts.

---

## 7. Database Migrations & Safe Reset Procedures

### Applying Pending Migrations
Migrations run automatically on `backend-api` startup. To manually execute migrations:
```bash
docker compose -p agentops exec backend-api alembic upgrade head
```

### Safe Database Reset (Data Reset without Volume Loss)
To safely reset application tables without wiping n8n workflows:
```bash
docker compose -p agentops exec backend-api python -c "
import asyncio
from app.db.base import Base
from app.db.session import async_engine

async def reset():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(reset())
"
docker compose -p agentops exec backend-api alembic stamp head
```

### Full Volume Reset (Destructive)
To completely recreate clean databases from scratch:
```bash
docker compose -p agentops down -v
docker compose -p agentops up -d
```
> [!CAUTION]
> `docker compose down -v` permanently destroys all stored research runs, audit trails, and n8n credentials.

---

## 8. Host-Specific Checks & Environment Status

| Check / Verification | Execution Method | Result | Notes |
| :--- | :--- | :--- | :--- |
| **Compose Schema Validation** | `docker compose -p agentops config` | **PASSED** | Syntax, resource limits, dependencies, and networks validated. |
| **Ollama Profile Schema** | `docker compose -p agentops --profile ollama config` | **PASSED** | Optional model container schema validated. |
| **Acceptance Test Suite** | `pytest test_compose_and_local_environment.py` | **PASSED (19/19)** | Port isolation, healthchecks, image reuse, persistence, and error handling verified. |
| **Frontend Standalone Build** | `npm --prefix apps/web run build` | **PASSED** | Standalone bundle and server.js verified. |
| **Live Docker Daemon Execution** | `docker ps` | *Host-Specific* | Requires Docker Desktop to be launched on macOS workstation (`open -a Docker`). |
