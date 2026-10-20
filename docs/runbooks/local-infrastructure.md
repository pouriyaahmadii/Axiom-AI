# Local Infrastructure Runbook (`docs/runbooks/local-infrastructure.md`)

This runbook documents the architecture, lifecycle management, security controls, and operational procedures for the local AgentOps infrastructure services managed via Docker Compose.

---

## 1. Architecture & Service Topology

AgentOps utilizes Docker Compose to establish an isolated, local runtime environment consisting of core persistent infrastructure services and application containers.

```
+-------------------------------------------------------------------------------+
| Host Machine (Developer Workstation)                                          |
|                                                                               |
|  [ Web Browser ] ──────> http://127.0.0.1:5678 (Loopback Only)                |
|                                   │                                           |
|  [ Local Python Host ] ───(optional override)───> 127.0.0.1:5432 / 6379       |
+───────────────────────────────────┼───────────────────────────────────────────+
                                    │
                                    ▼
+───────────────────────────────────────────────────────────────────────────────+
| Docker Network: `agentops-net` (Bridge, Isolated)                            |
|                                                                               |
|   +-----------------------+              +--------------------------------+   |
|   | Container:            |              | Container:                     |   |
|   | `agentops_n8n`        |              | `agentops_postgres`            |   |
|   | Image: n8n:1.70.0     |─────────────>| Image: postgres:16.4-alpine    |   |
|   | User: node (1000)     |  SQL (5432)  | DBs: agentops_db, n8n_db       |   |
|   +-----------------------+              +--------------------------------+   |
|               │                                       │                       |
|               ▼                                       ▼                       |
|        [n8n_data vol]                        [postgres_data vol]              |
|                                                                               |
|   +-----------------------+                                                   |
|   | Container:            |                                                   |
|   | `agentops_redis`      |                                                   |
|   | Image: redis:7.2.6    |                                                   |
|   +-----------------------+                                                   |
|               │                                                               |
|               ▼                                                               |
|        [redis_data vol]                                                       |
+───────────────────────────────────────────────────────────────────────────────+
```

### Pinned Service Specifications

| Service | Container Name | Image Tag | Default Host Binding | Internal Port | Volume Mount |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | `agentops_postgres` | `postgres:16.4-alpine` | *None* (Unpublished) | `5432` | `postgres_data:/var/lib/postgresql/data` |
| **Redis** | `agentops_redis` | `redis:7.2.6-alpine` | *None* (Unpublished) | `6379` | `redis_data:/data` |
| **n8n Community** | `agentops_n8n` | `n8nio/n8n:1.70.0` | `127.0.0.1:5678` (Loopback) | `5678` | `n8n_data:/home/node/.n8n` |

Application workloads (`backend-api`, `backend-worker`, `frontend`) are grouped under Docker Compose profile `app`. During infrastructure bootstrap, only the persistent data tier (`postgres`, `redis`, `n8n`) is started.

---

## 2. Security & Port Isolation Principles

### Unpublished Internal Ports by Default
In accordance with production-grade security standards and multi-tenant host isolation:
1. **Zero Host Exposure for Databases**: PostgreSQL (`5432`) and Redis (`6379`) do **not** publish ports to the host machine in base `compose.yaml`. They are only accessible to containers attached to `agentops-net`.
2. **Strict Loopback Binding**: Developer-facing HTTP interfaces (such as n8n on port `5678`, and eventually API `8000` / Web `3000`) bind strictly to `127.0.0.1`. They never bind to `0.0.0.0` or external network adapters.
3. **Workspace Port Reservations**: Per workspace guidelines (`AGENTS.md`), the following ports are strictly reserved for sibling projects and **must never be bound or killed**:
   - `8080`, `5433`, `6380`, `6333`.

### Optional Host Port Publishing (For Host-Native Python Development)
When developers run Python test suites, Alembic migrations, or worker scripts directly on the host machine outside Docker, host access to PostgreSQL (`5432`) and Redis (`6379`) is required.

To enable host ports cleanly without altering tracked git files:
```bash
cp compose.override.yaml.example compose.override.yaml
docker compose -p agentops up -d
```
Docker Compose automatically merges `compose.override.yaml` (which is ignored by `.gitignore`) and binds `127.0.0.1:5432` and `127.0.0.1:6379`.

---

## 3. PostgreSQL Multi-Database Initialization

AgentOps enforces strict database-level separation of duties between the core application engine and third-party orchestration workflows.

### Credential Separation Matrix

| Role | Default Username | Target Database | Privileges & Ownership |
| :--- | :--- | :--- | :--- |
| **Superuser** | `postgres_admin` | `postgres` | Cluster administration, role creation, init execution. |
| **AgentOps App** | `agentops_user` | `agentops_db` | Full schema and DDL ownership of `agentops_db`. Zero access to `n8n_db`. |
| **n8n Automation** | `n8n_user` | `n8n_db` | Full schema and DDL ownership of `n8n_db`. Zero access to `agentops_db`. |

### Initialization Script: `infra/postgres/init-databases.sh`
The script is mounted read-only into `/docker-entrypoint-initdb.d/init-databases.sh`.
- **First-Boot Execution**: The official PostgreSQL container executes all executable scripts in `/docker-entrypoint-initdb.d/` only when `postgres_data` is empty.
- **Idempotency**: All role and database creations use `IF NOT EXISTS` guards.
- **PostgreSQL 16 Permissions**: Starting in PostgreSQL 15+, the public schema permissions are revoked from `public`. The script explicitly grants `CREATE` and reassigns schema ownership to the target role:
  ```sql
  GRANT ALL ON SCHEMA public TO agentops_user;
  ALTER SCHEMA public OWNER TO agentops_user;
  ```

---

## 4. n8n Community Edition Configuration & Licensing

### Licensing Boundary
- **License**: n8n Community Edition is distributed under the **Sustainable Use License** (Fair-code).
- **Permitted Use**: You are free to self-host, run, customize, and automate internal business workflows, testing pipelines, and agent notifications within AgentOps without payment.
- **Commercial Boundary**: You cannot bundle or offer n8n as a commercial managed service or hosted SaaS platform competing with n8n Cloud.

### Persistent Encryption Key (`N8N_ENCRYPTION_KEY`)
> [!CRITICAL]
> n8n encrypts all stored credentials, tokens, and webhooks in `n8n_db` using `N8N_ENCRYPTION_KEY`.
> If this key is lost or rotated without re-encrypting credentials, all existing n8n workflows will fail to decrypt secrets.
> 
> Generate a cryptographically secure key for your `.env`:
> ```bash
> openssl rand -hex 32
> ```

### Privacy & Resource Settings
By default, the following flags are disabled in `compose.yaml` to ensure privacy, zero telemetry leakage, and fast startup:
- `N8N_DIAGNOSTICS_ENABLED=false`
- `N8N_VERSION_NOTIFICATIONS_ENABLED=false`
- `N8N_HIRING_BANNER_ENABLED=false`

---

## 5. Operational Commands & Lifecycle

All operations use the explicit project identifier `-p agentops`.

### Bootstrap Environment Configuration
```bash
# 1. Create local .env from example template
cp .env.example .env

# 2. Verify Docker Compose configuration
docker compose -p agentops config
```

### Starting the Infrastructure Services
```bash
# Starts postgres, redis, and n8n in the background
docker compose -p agentops up -d
```

### Inspecting Service Health
```bash
docker compose -p agentops ps
```
Expected output:
```
NAME                IMAGE                  COMMAND                  SERVICE    STATUS
agentops_postgres   postgres:16.4-alpine   "docker-entrypoint.s…"   postgres   Up (healthy)
agentops_redis      redis:7.2.6-alpine     "docker-entrypoint.s…"   redis      Up (healthy)
agentops_n8n        n8nio/n8n:1.70.0       "tini -- /docker-ent…"   n8n        Up (healthy)
```

### Monitoring Logs
```bash
# Follow logs for all infrastructure services
docker compose -p agentops logs -f

# Follow logs for specific service
docker compose -p agentops logs -f postgres
docker compose -p agentops logs -f n8n
```

### Graceful Shutdown (Non-Destructive)
```bash
# Stop containers without removing network or volumes
docker compose -p agentops stop

# Or stop and remove containers while preserving persistent volumes
docker compose -p agentops down
```
> [!NOTE]
> `docker compose down` preserves all named volumes (`postgres_data`, `redis_data`, `n8n_data`). Your database tables and n8n workflows remain completely intact.

---

## 6. Healthchecks & Diagnostics

### PostgreSQL Healthcheck
- Probe: `pg_isready -U postgres_admin -d postgres`
- Interval: 5s, Timeout: 5s, Retries: 5.
- Manual test inside container:
  ```bash
  docker compose -p agentops exec postgres pg_isready -U postgres_admin
  ```

### Redis Healthcheck
- Probe: `redis-cli ping` (Expects `PONG`)
- Interval: 5s, Timeout: 3s, Retries: 5.
- Manual test inside container:
  ```bash
  docker compose -p agentops exec redis redis-cli ping
  ```

### n8n Community Healthcheck
- Probe: `wget --no-verbose --tries=1 --spider http://127.0.0.1:5678/healthz || exit 1`
- Interval: 10s, Timeout: 5s, Retries: 5, Start period: 20s.
- Manual test from host:
  ```bash
  curl -fsS http://127.0.0.1:5678/healthz
  ```
  Expected HTTP response: `{"status":"ok"}`

---

## 7. Troubleshooting & Recovery

### Issue: Multi-Database Init Script Did Not Run
- **Symptom**: `agentops_db` or `n8n_db` does not exist; only default `postgres` exists.
- **Cause**: The PostgreSQL Docker entrypoint script only runs `/docker-entrypoint-initdb.d/` on an **empty** data directory. If `postgres_data` was initialized before the script was mounted, it skipped execution.
- **Resolution**:
  1. If existing data is unneeded:
     ```bash
     docker compose -p agentops down -v
     docker compose -p agentops up -d
     ```
  2. If preserving existing data, manually run the script via `exec`:
     ```bash
     docker compose -p agentops exec -T postgres sh /docker-entrypoint-initdb.d/init-databases.sh
     ```

### Issue: Port 5678 Already In Use on Host
- **Symptom**: `Bind for 127.0.0.1:5678 failed: port is already allocated`.
- **Diagnostic**: Check what process is listening on port 5678:
  ```bash
  lsof -i :5678
  ```
- **Rule Enforcement**: Never run `killall` or `pkill`. Identify the specific PID and terminate only the conflicting process.

### Destructive Command Safety Policy
- **Never Run**: `docker system prune -a` or `docker volume prune -f`.
- **Destructive Volume Wipe**: Wiping volumes (`docker compose down -v`) destroys all runs, state, and credentials. Always follow the procedures in [`docs/runbooks/backup-and-restore.md`](file:///Users/macbook/Downloads/Github_repo/agentops/docs/runbooks/backup-and-restore.md) before resetting volumes.
