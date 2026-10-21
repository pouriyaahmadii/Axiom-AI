# n8n Automation Workflows Integration (`docs/n8n-integration.md`)

## 1. Architectural Boundary & Philosophy

AgentOps uses **n8n Community Edition** as an external integration and workflow orchestration companion.

### Clear Division of Responsibilities
- **Python Backend (AgentOps Core)**: Remains the sole authority for:
  - Domain rules and schema validation
  - Research planning and bounded LangGraph agent runtime
  - LLM provider abstractions, retries, and rate limits
  - Evidence gathering, URL safety verification, and factual grounding
  - Persistent state machines, database transactions, and immutable audit logs
- **n8n Integration Workflows**: Restricted strictly to:
  - Ingesting incoming external webhooks and scheduled triggers
  - Transforming and validating input payloads before calling the AgentOps API
  - Formatted outbound notifications (Slack, email digests, incident alerts)
  - Distributing Human-in-the-Loop (HITL) approval requests with decision endpoints

```mermaid
flowchart LR
    ExternalUser["External System / Cron"] -->|Webhook / Schedule| n8n["n8n Orchestrator (1.70.0)"]
    n8n -->|POST /api/v1/runs (X-API-Key)| Backend["AgentOps FastAPI"]
    Backend -->|Async Task| CeleryWorker["Celery + LangGraph"]
    CeleryWorker -->|State Changes| DB[(PostgreSQL)]
    Backend -.->|Outbox / Webhook Event| n8n
    n8n -->|Safe Sink / Alert| Operator["Operator / Ops Sink"]
```

---

## 2. Pinned Version & Environment Setup

- **Pinned Image**: `n8nio/n8n:1.70.0`
- **Port Isolation**: Binds strictly to `127.0.0.1:5678` (never exposed publicly)
- **Compose Service**: `agentops_n8n` in `compose.yaml`
- **Internal Network**: `agentops_network` (bridge network shared with API, worker, PostgreSQL, Redis)

### Required Environment Variables
Inside n8n (configured in `compose.yaml` or `.env`):
| Variable | Description | Default (Local Dev) |
|---|---|---|
| `AGENTOPS_API_URL` | Base URL of AgentOps API | `http://agentops_api:8000` (Docker) or `http://127.0.0.1:8000` |
| `AGENTOPS_API_KEY` | Server-to-server secret API key | `agentops-dev-internal-key` |
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | Restricts config file permissions | `true` |

---

## 3. Workflow Catalog

All workflow templates are located in `workflows/n8n/` as well as categorized subdirectories (`triggers/` and `notifications/`):

| # | Workflow Name | Path | Trigger Type | Default Status |
|---|---|---|---|---|
| 01 | **AgentOps Run Trigger** | `workflows/n8n/01_agentops_run_trigger.json` | Webhook (`POST`) | Inactive (`false`) |
| 02 | **Run Completed Notification** | `workflows/n8n/02_run_completed_notification.json` | Webhook (`POST`) | Inactive (`false`) |
| 03 | **Run Failure Notification** | `workflows/n8n/03_run_failure_notification.json` | Webhook (`POST`) | Inactive (`false`) |
| 04 | **Approval Required Notification** | `workflows/n8n/04_approval_required_notification.json` | Webhook (`POST`) | Inactive (`false`) |
| 05 | **Scheduled Research Trigger** | `workflows/n8n/05_scheduled_research_trigger.json` | Schedule (Weekly) | Inactive (`false`) |

---

## 4. Workflow Specifications

### Workflow 01: AgentOps Run Trigger (`01_agentops_run_trigger.json`)
- **Purpose**: Validates incoming research requests, enforces security limits (50KB max payload, 10-2000 char objective, 2-100 char domain), generates correlation and idempotency keys, and submits the run asynchronously to `POST /api/v1/runs`.
- **Webhook Path**: `agentops-run-trigger`
- **HTTP Method**: `POST`
- **Authentication**: Backend requires `X-API-Key: {{$env.AGENTOPS_API_KEY}}`.
- **Sample Request Payload**:
  ```json
  {
    "objective": "Comprehensive competitor landscape analysis of AI agent observability platforms in Q4 2026",
    "domain": "ai-observability",
    "geography": "Global"
  }
  ```
- **Responses**:
  - `202 Accepted`: Run submitted and enqueued in background.
  - `400 Bad Request`: Payload validation failed (e.g. objective too short or payload > 50KB).
  - `502 Bad Gateway`: AgentOps backend API unreachable or returned an error.

---

### Workflow 02: Run Completed Notification (`02_run_completed_notification.json`)
- **Purpose**: Receives completion events, queries the backend for the generated research report (`GET /api/v1/runs/{run_id}/report`), generates a clean Markdown summary, and dispatches the alert to the notification sink.
- **Webhook Path**: `agentops-run-completed`
- **HTTP Method**: `POST`
- **Safe Demo Sink**: Dispatches to a `Safe Demo Logger` (`n8n-nodes-base.noOp`) so it can be demonstrated without configuring third-party Slack or email credentials.
- **Sample Event Payload**:
  ```json
  {
    "event_type": "RUN_COMPLETED",
    "run_id": "11111111-2222-3333-4444-555555555555",
    "completed_at": "2026-10-21T20:00:00Z"
  }
  ```
- **Responses**:
  - `200 OK`: Report retrieved and formatted notification delivered.
  - `400 Bad Request`: Missing or invalid `run_id` (must be UUID).
  - `502 Bad Gateway`: Report could not be fetched from backend.

---

### Workflow 03: Run Failure Notification (`03_run_failure_notification.json`)
- **Purpose**: Ingests failure notifications (`RUN_FAILED`), retrieves recent audit event history (`GET /api/v1/runs/{run_id}/events?limit=10`), structures a high-severity alert for operators, and logs to the incident sink.
- **Webhook Path**: `agentops-run-failed`
- **HTTP Method**: `POST`
- **Safe Demo Sink**: Dispatches to `Safe Demo Logger (Incident Sink)`.
- **Sample Event Payload**:
  ```json
  {
    "event_type": "RUN_FAILED",
    "run_id": "11111111-2222-3333-4444-555555555555",
    "error_message": "BudgetExceededError: Estimated execution cost exceeded $10.00 ceiling limit",
    "failed_at": "2026-10-21T20:05:00Z"
  }
  ```
- **Responses**:
  - `200 OK`: Incident formatted and alerted.
  - `400 Bad Request`: Malformed failure event payload.

---

### Workflow 04: Approval Required Notification (`04_approval_required_notification.json`)
- **Purpose**: Triggers when an agent run hits a Human-in-the-Loop checkpoint (`APPROVAL_REQUESTED`). Generates actionable endpoint links for approval or rejection (`/api/v1/approvals/{id}/approve` and `/reject`), formats payload diffs, and alerts operators.
- **Webhook Path**: `agentops-approval-required`
- **HTTP Method**: `POST`
- **Safe Demo Sink**: Dispatches to `Safe Demo Logger (Approval Sink)`.
- **Sample Event Payload**:
  ```json
  {
    "approval_id": "88888888-9999-aaaa-bbbb-cccccccccccc",
    "run_id": "11111111-2222-3333-4444-555555555555",
    "action": "PLAN_REVIEW",
    "payload_hash": "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
    "expires_at": "2026-10-22T20:00:00Z",
    "proposed_action": {
      "total_steps": 5,
      "requires_search": true
    }
  }
  ```
- **Actionable Links Provided in Alert**:
  - **Approve**: `POST /api/v1/approvals/{approval_id}/approve`
  - **Reject**: `POST /api/v1/approvals/{approval_id}/reject`

---

### Workflow 05: Scheduled Research Trigger (`05_scheduled_research_trigger.json`)
- **Purpose**: Runs a recurring competitive research scan every Monday at 08:00 UTC. Inactive by default.
- **Trigger Type**: `n8n-nodes-base.scheduleTrigger` (Rule: weekly, Monday 08:00).
- **Idempotency Strategy**: Generates a deterministic date-keyed idempotency key (`scheduled-weekly-scan-YYYY-MM-DD`) ensuring re-runs on the same day are deduplicated by the AgentOps backend.
- **Safety**: Inactive by default (`"active": false`) to prevent accidental automated executions without explicit operator activation.

---

## 5. Import Instructions

### Option A: Using the n8n Web UI
1. Navigate to `http://localhost:5678` in your browser.
2. In the left navigation menu, click **Workflows**.
3. In the top-right corner, click **Add Workflow** (or the `...` menu) -> **Import from File**.
4. Select the desired JSON file from `workflows/n8n/`.
5. Review the imported nodes and activate the workflow if desired.

### Option B: Using the n8n CLI
To batch-import all workflows directly inside the Docker container:
```bash
docker compose -p agentops exec agentops_n8n n8n import:workflow --input=/workflows/n8n/01_agentops_run_trigger.json
docker compose -p agentops exec agentops_n8n n8n import:workflow --input=/workflows/n8n/02_run_completed_notification.json
docker compose -p agentops exec agentops_n8n n8n import:workflow --input=/workflows/n8n/03_run_failure_notification.json
docker compose -p agentops exec agentops_n8n n8n import:workflow --input=/workflows/n8n/04_approval_required_notification.json
docker compose -p agentops exec agentops_n8n n8n import:workflow --input=/workflows/n8n/05_scheduled_research_trigger.json
```

---

## 6. Manual Testing & Verification

Ensure the backend is running (`http://127.0.0.1:8000`) and n8n is running (`http://127.0.0.1:5678`).

### 1. Test Run Trigger
```bash
curl -i -X POST http://127.0.0.1:5678/webhook/agentops-run-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Verify competitive positioning against Langfuse and LangSmith",
    "domain": "ai-observability"
  }'
```
Expected output: `HTTP/1.1 202 Accepted` with `run_id` and `idempotency_key`.

### 2. Test Input Validation Rejection
```bash
curl -i -X POST http://127.0.0.1:5678/webhook/agentops-run-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Too short",
    "domain": "ai"
  }'
```
Expected output: `HTTP/1.1 400 Bad Request` with `VALIDATION_ERROR`.

### 3. Test Completion Notification
```bash
curl -i -X POST http://127.0.0.1:5678/webhook/agentops-run-completed \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "RUN_COMPLETED",
    "run_id": "00000000-0000-0000-0000-000000000001"
  }'
```

---

## 7. Security and Operational Hardening

1. **No Embedded Secrets**: No API keys, passwords, or tokens are hardcoded into workflow node parameters. All authentication references `{{ $env.AGENTOPS_API_KEY }}`.
2. **Payload Size Guardrails**: Every webhook entrypoint verifies `JSON.stringify(payload).length <= 51200` (50KB) and immediately rejects oversized payloads with HTTP 400.
3. **Idempotency Guardrails**: All trigger workflows submit explicit `idempotency_key` values. Duplicate requests are handled gracefully by AgentOps' database uniqueness constraint without duplicating work.
4. **Network Isolation**: n8n runs in the private `agentops_network`. The n8n port is bound to loopback `127.0.0.1:5678`, avoiding any public internet exposure.
5. **Safe Default Sinks**: All notification workflows default to a `NoOp` demonstration sink, avoiding external dependencies or paid third-party accounts during evaluation.
