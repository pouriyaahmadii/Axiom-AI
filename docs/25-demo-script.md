# AgentOps: End-to-End Demonstration Script (`docs/25-demo-script.md`)

This document provides a repeatable, verifiable demonstration script for the AgentOps platform. It walks an evaluator through the core capabilities of the platform using 100% synthetic and openly licensed data in deterministic Mock mode, requiring zero paid external API credentials.

---

## 1. Demonstration Overview & Scenarios

The demonstration covers four sequential operational scenarios:
1. **Scenario A: Golden Path Research Run** — Submitting a research objective, automated DAG planning, sandboxed tool execution, evidence extraction, citation auditing, and report generation.
2. **Scenario B: Traceable Evidence & Source Grounding** — Inspecting source content hashes, citation-to-evidence links, and grounded claims versus analytical inferences.
3. **Scenario C: Human-in-the-Loop (HITL) Approval Gate** — Execution checkpointing, state freezing, operator payload review, and continuation without duplicate execution.
4. **Scenario D: Failure Handling, Bounded Retry, and Plan Repair** — Simulating an unrecoverable step failure, bounded planner repair attempt, and safe failure state transition.

---

## 2. Environment Preparation

Ensure the repository dependencies are installed and the deterministic mock configuration is active.

```bash
# 1. Activate Python virtual environment
source .venv/bin/activate

# 2. Configure deterministic mock environment
export ENVIRONMENT=development
export LLM_PROVIDER=mock
export SEARCH_PROVIDER=mock
export MOCK_DETERMINISTIC_SEED=42
export API_KEY=agentops-dev-internal-key
export DATABASE_URL="postgresql+asyncpg://agentops_user:agentops_pass@127.0.0.1:5432/agentops_db"
export SYNC_DATABASE_URL="postgresql://agentops_user:agentops_pass@127.0.0.1:5432/agentops_db"
export REDIS_URL="redis://127.0.0.1:6379/0"
```

---

## 3. Scenario A: Golden Path Research Run

### Step A.1: Submit Research Objective
Submit a research request to analyze enterprise issue tracking software:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: agentops-dev-internal-key" \
  -d '{
    "objective": "Compare Linear and Jira enterprise pricing, SLAs, and target customer segments in North America",
    "domain": "software",
    "geography": "North America",
    "idempotency_key": "demo-run-linear-jira-001"
  }'
```

**Actual Response (`202 Accepted`):**
```json
{
  "run_id": "70cf52eb-72e0-4ea4-abbf-a0377e565683",
  "status": "QUEUED",
  "created_at": "2026-10-22T00:15:00.000Z"
}
```

### Step A.2: Execution Lifecycle & Node Transitions
The Celery worker dequeues the run and triggers the LangGraph state machine:
1. `validate_request`: Validates objective length, character sanitization, and domain bounds.
2. `generate_plan`: Mock LLM generates a 3-step dependency DAG (`discover_competitors` → `search_public_web` → `fetch_approved_public_page`).
3. `validate_plan`: Confirms DAG acyclicity, step count ($\le 10$), and tool registry approval.
4. `execute_task`: Dispatches tasks inside the Safe Tool Sandbox with SSRF defenses and in-memory document caching.
5. `validate_step_result`: Extracts normalized source records and content hashes.
6. `generate_report`: Compiles structured findings and claims.
7. `validate_report`: Audits citation coverage and verifies evidence references.
8. `finalize_run`: Commits final status `COMPLETED`.

### Step A.3: Retrieve Completed Run State
```bash
curl -s http://127.0.0.1:8000/api/v1/runs/70cf52eb-72e0-4ea4-abbf-a0377e565683 \
  -H "X-API-Key: agentops-dev-internal-key"
```

**Actual Response Extract (`200 OK`):**
```json
{
  "run_id": "70cf52eb-72e0-4ea4-abbf-a0377e565683",
  "objective": "Compare Linear and Jira enterprise pricing, SLAs, and target customer segments in North America",
  "status": "COMPLETED",
  "llm_provider": "mock",
  "search_provider": "mock",
  "plan": {
    "total_steps": 3,
    "steps": [
      {
        "step_identifier": "search_market_landscape",
        "title": "Search Market Landscape",
        "tool_name": "web_search",
        "status": "COMPLETED"
      },
      {
        "step_identifier": "fetch_competitor_documentation",
        "title": "Fetch Competitor Documentation",
        "tool_name": "fetch_document",
        "status": "COMPLETED"
      },
      {
        "step_identifier": "extract_competitive_metrics",
        "title": "Extract Competitive Metrics",
        "tool_name": "extract_metrics",
        "status": "COMPLETED"
      }
    ]
  }
}
```

---

## 4. Scenario B: Traceable Evidence & Source Grounding

### Step B.1: Inspect Retrieved Sources
Query the sources collected during the run:

```bash
curl -s "http://127.0.0.1:8000/api/v1/runs/70cf52eb-72e0-4ea4-abbf-a0377e565683/sources" \
  -H "X-API-Key: agentops-dev-internal-key"
```

**Output Structure:**
```json
{
  "items": [
    {
      "source_id": "src-linear-pricing",
      "url": "https://example.com/linear/pricing",
      "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "retrieval_status": "SUCCESS",
      "retrieved_at": "2026-10-22T00:15:02.124Z"
    }
  ],
  "total": 1
}
```

### Step B.2: Inspect Final Report & Grounded Claims
```bash
curl -s "http://127.0.0.1:8000/api/v1/runs/70cf52eb-72e0-4ea4-abbf-a0377e565683/report" \
  -H "X-API-Key: agentops-dev-internal-key"
```

**Report JSON Output:**
```json
{
  "title": "Competitive Analysis: Linear vs Jira",
  "grounded_findings": "Linear Enterprise pricing is published at $28 per user/month annually with 99.9% uptime SLA.",
  "strategic_inferences": "Linear targets high-velocity product teams, whereas Jira Enterprise emphasizes complex enterprise governance and audit capabilities.",
  "citation_coverage": 1.0,
  "claims": [
    {
      "claim_text": "Linear Enterprise costs $28 per user/month with 99.9% uptime SLA",
      "claim_type": "DIRECT_FACT",
      "evidence_ids": ["evi-linear-sla-01"],
      "verified": true
    }
  ]
}
```

---

## 5. Scenario C: Human-in-the-Loop (HITL) Approval Gate

When an action or plan requires human authorization (e.g. high-risk actions, consequential research budgets, or report sign-off):

### Step C.1: Run Pauses at Approval Checkpoint
The LangGraph runtime interrupts execution before entering the target node, updates the run state to `AWAITING_APPROVAL`, and persists a durable checkpoint in PostgreSQL.

```bash
curl -s http://127.0.0.1:8000/api/v1/approvals/pending \
  -H "X-API-Key: agentops-dev-internal-key"
```

**Response:**
```json
{
  "items": [
    {
      "approval_id": "appr-89b1c2d3-4567-890a-bcde-f01234567890",
      "run_id": "70cf52eb-72e0-4ea4-abbf-a0377e565683",
      "step_identifier": "final_report_review",
      "action_type": "REPORT_SIGNOFF",
      "status": "PENDING",
      "payload": {
        "title": "Competitive Analysis: Linear vs Jira",
        "claim_count": 1
      }
    }
  ],
  "total": 1
}
```

### Step C.2: Operator Submits Approval
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/approvals/89b1c2d3-4567-890a-bcde-f01234567890/approve" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: agentops-dev-internal-key" \
  -H "X-Operator-Id: lead_researcher@agentops.local" \
  -d '{
    "operator_notes": "Verified claim against cited pricing documentation."
  }'
```

**Response (`200 OK`):**
```json
{
  "approval_id": "89b1c2d3-4567-890a-bcde-f01234567890",
  "run_id": "70cf52eb-72e0-4ea4-abbf-a0377e565683",
  "action": "step_execution",
  "status": "APPROVED",
  "run_status": "RUNNING",
  "operator_notes": "Verified claim against cited pricing documentation.",
  "resolved_by": "lead_researcher@agentops.local",
  "resolved_at": "2026-10-22T00:16:30.000Z"
}
```
The Celery worker resumes the graph from the persisted checkpoint without re-executing previous steps.

---

## 6. Scenario D: Failure Handling, Retry, and Bounded Repair

### Step D.1: Simulating an Unrecoverable Failure
Submit an invalid plan or a request that violates budget bounds:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: agentops-dev-internal-key" \
  -d '{
    "objective": "A",
    "domain": "unknown_domain_fail",
    "idempotency_key": "demo-invalid-request-001"
  }'
```

**Response (`422 Unprocessable Entity`):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input validation failed: objective must be at least 10 characters.",
    "correlation_id": "c1a2b3c4-5678-90ab-cdef-1234567890ab"
  }
}
```

### Step D.2: Bounded Plan Repair
When a generated plan has structural anomalies (e.g. cyclic dependencies):
1. `validate_plan_node` detects the cycle.
2. Increments `plan_repair_attempts`.
3. If `plan_repair_attempts <= MAX_PLAN_REPAIR_ATTEMPTS` (default 2), it routes back to `generate_plan` with repair instructions.
4. If repairs are exhausted, it halts safely with status `FAILED` and records an audit event. Zero expensive LLM tool calls are made for broken plans.

---

## 7. Verification Summary
All scenarios above are backed by automated tests:
```bash
# Verify the entire end-to-end scenario suite
pytest services/backend/tests/integration/test_durable_execution.py -v
pytest services/backend/tests/integration/test_hitl_approval_and_resumption.py -v
pytest services/backend/tests/evals/test_agent_evals.py -v
```
