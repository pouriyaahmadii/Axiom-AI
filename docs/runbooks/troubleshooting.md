# Operational Troubleshooting Runbook (`docs/runbooks/troubleshooting.md`)

This runbook provides diagnostic workflows, error code references, log inspection procedures, and tactical remediations for common operational issues encountered when running AgentOps.

---

## 1. Quick Triage Flowchart

```text
Problem Detected
  │
  ├──► [API returns 500 or fails to boot]
  │      └── Check Section 3: Database Connectivity & Migrations
  │
  ├──► [Runs remain stuck in QUEUED state]
  │      └── Check Section 4: Redis & Celery Worker Issues
  │
  ├──► [HTTP 401 / 403 / 422 on API requests]
  │      └── Check Section 5: Ingress API & Networking Issues
  │
  ├──► [n8n webhooks fail or notifications not received]
  │      └── Check Section 6: n8n Automation & Webhook Issues
  │
  ├──► [Tool execution fails with security error or SSRF block]
  │      └── Check Section 7: Safe Tool Sandbox & Security Triggers
  │
  ├──► [Runs terminate early with FAILED status and budget error]
  │      └── Check Section 8: Budget Exhaustion & Execution Limits
  │
  └──► [Frontend displays disconnected state or proxy errors]
         └── Check Section 9: Next.js Frontend Issues
```

---

## 2. Global Diagnostic Commands

Execute these baseline diagnostics to determine system health across the stack:

```bash
# 1. Check all container states and healthchecks
docker compose -p agentops ps

# 2. Inspect real-time structured logs with correlation ID filter
docker compose -p agentops logs -f api worker | grep -E '"level":"(ERROR|WARNING)"'

# 3. Check loopback port allocations
lsof -iTCP:3000,8000,5432,6379,5678 -sTCP:LISTEN

# 4. Verify API health endpoint directly
curl -s http://127.0.0.1:8000/health | jq .

# 5. Inspect active Celery worker queues and registered tasks
source .venv/bin/activate
celery -A services.backend.app.workers.celery_app inspect active
```

---

## 3. Database Connectivity & Migrations

### Issue 3.1: Connection Refused on Port 5432
- **Symptoms**: FastAPI fails to start with `ConnectionRefusedError: [Errno 61] Connect call failed ('127.0.0.1', 5432)` or Celery worker repeatedly logs connection retries.
- **Root Causes**:
  1. The `agentops_postgres` container is stopped or restarting due to an initialization failure.
  2. PostgreSQL is listening inside Docker but port forwarding to `127.0.0.1:5432` failed.
- **Diagnostic Steps**:
  ```bash
  # Check PostgreSQL container logs
  docker compose -p agentops logs postgres
  
  # Check PostgreSQL socket responsiveness
  docker compose -p agentops exec postgres pg_isready -U agentops_user -d agentops_db
  ```
- **Remediation**:
  1. If container exited with permissions error on volume, ensure correct directory permissions.
  2. Restart the database service:
     ```bash
     docker compose -p agentops restart postgres
     ```

### Issue 3.2: `asyncpg.exceptions.TooManyConnectionsError`
- **Symptoms**: API returns HTTP 500 with `asyncpg.exceptions.TooManyConnectionsError: remaining connection slots are reserved for non-replication superuser connections`.
- **Root Cause**: Database connection pool exhaustion caused by high concurrent request volume or leaked sessions.
- **Remediation**:
  1. Inspect active connections:
     ```bash
     docker compose -p agentops exec postgres psql -U agentops_user -d agentops_db \
       -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
     ```
  2. Adjust pool size in `.env` if workload requires higher capacity:
     ```bash
     DB_POOL_SIZE=20
     DB_MAX_OVERFLOW=10
     ```
  3. Restart the API service to release leaked connections:
     ```bash
     docker compose -p agentops restart api
     ```

### Issue 3.3: Alembic Schema Migration Divergence
- **Symptoms**: API boots but immediately crashes with `alembic.util.exc.CommandError: Target database is not up to date.`
- **Diagnostic Steps**:
  ```bash
  source .venv/bin/activate
  cd services/backend
  alembic current
  alembic heads
  ```
- **Remediation**:
  Apply pending revisions to synchronize schema:
  ```bash
  alembic upgrade head
  ```

---

## 4. Redis & Celery Worker Issues

### Issue 4.1: Runs Stuck in `QUEUED` State
- **Symptoms**: A run is submitted, API returns `202 Accepted`, but status remains `QUEUED` indefinitely and no step events appear.
- **Root Causes**:
  1. Celery worker is not running or crashed silently.
  2. Worker is subscribed to the wrong queue name.
  3. Redis broker is full or unreachable.
- **Diagnostic Steps**:
  ```bash
  # Check Celery worker container status
  docker compose -p agentops logs worker --tail=100
  
  # Inspect pending Redis queue length
  docker compose -p agentops exec redis redis-cli LLEN agentops_tasks
  
  # Inspect Celery ping response
  celery -A services.backend.app.workers.celery_app inspect ping
  ```
- **Remediation**:
  1. If queue length is $>0$ but no worker is processing, restart the worker:
     ```bash
     docker compose -p agentops restart worker
     ```
  2. If tasks fail with deserialization errors, ensure both API and worker are running the same image revision.

### Issue 4.2: Worker Task Timeout (`TimeLimitExceeded`)
- **Symptoms**: Worker task abruptly terminates with `celery.exceptions.TimeLimitExceeded: TimeLimitExceeded(300,)`.
- **Root Cause**: An external tool or LangGraph state machine exceeded the hard 300-second execution budget ceiling.
- **Remediation**:
  1. Locate the timing trace via correlation ID:
     ```bash
     docker compose -p agentops logs worker | grep '<correlation_id>'
     ```
  2. Verify whether an external provider (e.g., Tavily or Ollama) experienced network hanging.
  3. The database record will automatically be marked `FAILED` with error category `TIMEOUT`.

---

## 5. Ingress API & Networking Issues

### Issue 5.1: Port 8000 Conflict (`Address already in use`)
- **Symptoms**: API service fails to bind on host: `OSError: [Errno 48] Address already in use`.
- **Remediation**:
  Find the PID bound to 8000 and terminate it:
  ```bash
  lsof -iTCP:8000 -sTCP:LISTEN
  # Terminate specific PID associated with this workspace
  kill -15 <PID>
  ```

### Issue 5.2: HTTP 401 Unauthorized / Invalid API Key
- **Symptoms**: Ingress requests receive:
  ```json
  {"detail": "Invalid or missing API key"}
  ```
- **Root Cause**: Missing or mismatched `X-API-Key` header.
- **Remediation**:
  1. Verify the configured key in `.env`:
     ```bash
     grep "^API_KEY=" .env
     ```
  2. Include the exact header in requests:
     ```bash
     curl -H "X-API-Key: <your_api_key>" http://127.0.0.1:8000/api/v1/runs
     ```

### Issue 5.3: HTTP 422 Unprocessable Entity
- **Symptoms**: Run submission rejected with 422 status and JSON field errors.
- **Root Cause**: Objective failed validation constraints (empty, $>1000$ characters, or contains illegal control characters).
- **Remediation**:
  Ensure the objective is between 10 and 1000 characters and provides a valid domain string:
  ```json
  {
    "objective": "Compare Linear and Jira enterprise pricing and target customer segments",
    "domain": "software"
  }
  ```

---

## 6. n8n Automation & Webhook Issues

### Issue 6.1: Webhook HMAC Signature Mismatch (HTTP 401)
- **Symptoms**: n8n workflow execution node fails with `401 Unauthorized: HMAC signature verification failed`.
- **Root Causes**:
  1. Mismatched `N8N_WEBHOOK_SECRET` between `.env` and n8n environment.
  2. Malformed `X-AgentOps-Signature` header format (must be `sha256=<hex_digest>`).
  3. Payload altered in transit or JSON whitespace normalized after signature generation.
- **Remediation**:
  1. Confirm secret parity:
     ```bash
     docker compose -p agentops exec api env | grep N8N_WEBHOOK_SECRET
     docker compose -p agentops exec n8n env | grep N8N_WEBHOOK_SECRET
     ```
  2. Generate HMAC using the raw UTF-8 request body bytes before parsing.

### Issue 6.2: Timestamp Anti-Replay Rejection
- **Symptoms**: Webhook rejected with `Webhook timestamp drift exceeds tolerance (300s)`.
- **Root Cause**: Host system clock drift or delayed webhook delivery exceeding the 5-minute replay window.
- **Remediation**:
  Synchronize host NTP clock or inspect network latency between n8n and API.

---

## 7. Safe Tool Sandbox & Security Triggers

### Issue 7.1: SSRF Block (`SSRFValidationError`)
- **Symptoms**: `fetch_web_page` tool fails with:
  ```text
  SSRFValidationError: Access to destination IP '169.254.169.254' is blocked (Cloud Metadata / Link-Local)
  ```
- **Root Cause**: The agent generated or followed a URL targeting private networks (RFC 1918), AWS/GCP metadata services, or loopback interfaces.
- **Resolution**:
  This is expected, defensive behavior. The platform blocks the request to protect host infrastructure. The LangGraph state machine will record the security violation and transition to fallback search or bounded plan repair.

### Issue 7.2: Unknown Tool Invocation Rejected
- **Symptoms**: Run fails with `UnknownToolError: Tool 'execute_bash' is not registered in the Safe Tool Sandbox`.
- **Root Cause**: An LLM generated a plan requesting unauthorized system execution.
- **Resolution**:
  AgentOps strictly allowlists approved tools (`web_search`, `fetch_web_page`). Arbitrary shell, SQL, or Python code execution is an explicit non-goal and permanently blocked.

---

## 8. Budget Exhaustion & Execution Limits

### Issue 8.1: Financial Dollar Ceiling Reached
- **Symptoms**: Run fails with `ExecutionBudgetExceeded: Run cost $1.02 exceeds hard ceiling $1.00`.
- **Remediation**:
  1. If running live external LLM providers (e.g., OpenAI `gpt-4o`), inspect token consumption in the run detail timeline.
  2. In development or mock mode, costs are strictly $0.00.
  3. Adjust `MAX_RUN_COST_USD` in `.env` if extended analysis is required.

### Issue 8.2: Maximum Steps Exceeded
- **Symptoms**: Run terminates with `MaxStepsExceeded: Plan steps (12) exceeds maximum allowed (10)`.
- **Remediation**:
  The planner prompt enforces $\le 10$ steps. If complex research requires more steps, divide the objective into discrete, sequential runs.

---

## 9. Next.js Frontend Issues

### Issue 9.1: Frontend API Proxy Disconnected (`ECONNREFUSED`)
- **Symptoms**: Next.js UI displays red connection banner: `Unable to connect to AgentOps API Gateway`.
- **Diagnostic Steps**:
  ```bash
  # Check if backend API is responding on loopback
  curl -s http://127.0.0.1:8000/health
  ```
- **Remediation**:
  1. In Docker Compose, the frontend reaches the backend via `http://api:8000`. Ensure `BACKEND_INTERNAL_URL=http://api:8000` is set in the container environment.
  2. For local standalone development, ensure `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` is present in `apps/web/.env.local`.

### Issue 9.2: Stale Build Artifacts or Hydration Errors
- **Remediation**:
  Wipe the local Next.js cache and rebuild:
  ```bash
  rm -rf apps/web/.next
  npm --prefix apps/web run build
  ```

---

## 10. Operational Health Check Checklist

Before escalating any issue, confirm:
1. `docker compose -p agentops ps` shows all 6 containers `Up (healthy)`.
2. PostgreSQL has free disk space on the Docker host (`df -h`).
3. Memory utilization is within bounded thresholds ($< 512\text{ MB}$ per worker).
4. No forbidden ports (`8080`, `6333`, `5433`, `6380`) are bound or interfered with.
