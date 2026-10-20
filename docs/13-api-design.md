# API Design Specification: AgentOps

## 1. REST Architecture & Conventions

The AgentOps API adheres strictly to RESTful resource modeling over HTTP/JSON with OpenAPI 3.1 specification generation via FastAPI.

### 1.1 Global Headers
- `X-Correlation-ID`: Client-supplied or server-generated UUID tracking the request lifecycle across logs and traces.
- `Content-Type`: `application/json` for all POST/PUT bodies.
- `X-AgentOps-Signature`: HMAC-SHA256 signature required on webhook endpoints.

### 1.2 Error Response Envelope
All non-2xx responses conform to a unified error schema:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Step parameters failed schema verification.",
    "correlation_id": "c1f7b4e9-1234-4567-89ab-cdef01234567",
    "details": [
      {
        "field": "objective",
        "issue": "String should have at least 10 characters"
      }
    ]
  }
}
```

---

## 2. API v1 Endpoints Catalog

### 2.1 System & Health

#### `GET /api/v1/health`
Checks operational readiness of API and upstream database/broker dependencies.
- **Response 200 OK**:
```json
{
  "status": "ok",
  "app_name": "AgentOps",
  "environment": "development",
  "llm_provider": "mock",
  "search_provider": "mock",
  "database": "connected",
  "redis": "connected"
}
```

#### `GET /api/v1/info`
Exposes system constraints and runtime bounds.
- **Response 200 OK**:
```json
{
  "version": "0.1.0",
  "limits": {
    "max_plan_steps": 10,
    "max_execution_seconds": 300,
    "step_timeout_seconds": 60,
    "budget_usd_limit": 1.00
  },
  "providers": {
    "llm": "mock",
    "search": "mock"
  }
}
```

---

### 2.2 Research Runs Management

#### `POST /api/v1/runs`
Submits a new analytical research objective for execution.
- **Request Body**:
```json
{
  "objective": "Analyze top 3 AI code completion tools in North America comparing features and pricing.",
  "domain": "software-development",
  "geography": "North America",
  "constraints": {
    "max_competitors": 3
  },
  "provider_override": {
    "llm": "mock",
    "search": "mock"
  }
}
```
- **Response 201 Created**:
```json
{
  "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "QUEUED",
  "created_at": "2026-10-20T10:30:00Z"
}
```
- **Response 422 Unprocessable Entity**: When schema validation fails.

#### `GET /api/v1/runs`
Lists historical runs with pagination and status filters.
- **Query Parameters**:
  - `status` (optional string): Filter by run status.
  - `limit` (optional integer, default: 20, max: 100).
  - `offset` (optional integer, default: 0).
- **Response 200 OK**:
```json
{
  "items": [
    {
      "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "objective": "Analyze top 3 AI code completion tools...",
      "status": "COMPLETED",
      "created_at": "2026-10-20T10:30:00Z",
      "completed_at": "2026-10-20T10:30:04Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### `GET /api/v1/runs/{id}`
Retrieves detailed state of a specific run, including its execution plan and active step.
- **Response 200 OK**:
```json
{
  "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "AWAITING_APPROVAL",
  "objective": "Analyze top 3 AI code completion tools...",
  "current_step_index": 4,
  "plan": {
    "total_steps": 5,
    "steps": [
      {
        "step_id": "c1f7b4e9-1111-2222-3333-444455556666",
        "step_index": 0,
        "title": "Search for market leading code assistants",
        "tool_name": "web_search",
        "status": "COMPLETED"
      },
      {
        "step_id": "c1f7b4e9-7777-8888-9999-000011112222",
        "step_index": 4,
        "title": "Synthesize final competitor teardown report",
        "tool_name": "synthesize_report",
        "status": "PENDING",
        "requires_human_approval": true
      }
    ]
  },
  "approval_pending": {
    "approval_id": "e2a3c4d5-0000-1111-2222-333344445555",
    "proposed_action": {
      "summary": "Generate public competitor teardown report"
    }
  }
}
```

#### `POST /api/v1/runs/{id}/cancel`
Requests graceful cancellation of an active run.
- **Response 200 OK**:
```json
{
  "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "CANCELLED",
  "message": "Run execution cancelled by operator request."
}
```

---

### 2.3 Human-in-the-Loop (HITL) Gate

#### `POST /api/v1/runs/{id}/approvals/{approval_id}`
Submits operator verdict to resume or abort a paused run.
- **Request Body**:
```json
{
  "verdict": "approved",
  "operator_notes": "Scope validated. Proceed to report generation."
}
```
- **Response 200 OK**:
```json
{
  "approval_id": "e2a3c4d5-0000-1111-2222-333344445555",
  "status": "APPROVED",
  "run_status": "RUNNING",
  "resolved_at": "2026-10-20T10:32:00Z"
}
```
- **Response 400 Bad Request**: If approval request is already resolved or expired.

---

### 2.4 Evidence & Final Report

#### `GET /api/v1/runs/{id}/evidence`
Retrieves all immutable evidence snippets captured by tools during execution.
- **Response 200 OK**:
```json
{
  "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "evidence": [
    {
      "evidence_id": "ev-01",
      "source_url": "https://example.com/pricing",
      "content_hash": "a1b2c3d4e5f6...",
      "raw_snippet": "Pro tier pricing is $19/user/month billed annually.",
      "retrieved_at": "2026-10-20T10:30:02Z"
    }
  ]
}
```

#### `GET /api/v1/runs/{id}/report`
Retrieves the synthesized research report with structured citation mappings.
- **Response 200 OK**:
```json
{
  "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "executive_summary": "Teardown of top 3 AI assistants in North America...",
  "markdown_content": "# Competitor Analysis...\n\n## Empirical Findings\nProduct A costs $19/mo[^ev-01].",
  "citations": [
    {
      "marker": "[^ev-01]",
      "evidence_id": "ev-01",
      "source_url": "https://example.com/pricing"
    }
  ],
  "created_at": "2026-10-20T10:30:04Z"
}
```

---

### 2.5 Automation & External Webhooks

#### `POST /api/v1/webhooks/n8n/trigger`
Allows n8n or external cron runners to initiate a research run securely.
- **Headers**:
  - `X-AgentOps-Signature`: HMAC-SHA256 signature.
- **Request Body**:
```json
{
  "objective": "Weekly competitor scan: DevTools sector",
  "domain": "software"
}
```
- **Response 202 Accepted**: Returns `run_id` and execution status.
