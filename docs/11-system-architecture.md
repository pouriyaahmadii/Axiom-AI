# System Architecture: AgentOps

## 1. System Overview & Context

**AgentOps** is a self-hosted AI Agent Operations Platform engineered to provide deterministic, observable, bounded, and auditable execution of research and analysis workflows. It is built around a **Single Coordinator Architecture** in Python, delegating async tasks to background workers and persisting durable state to PostgreSQL.

### 1.1 System Context Diagram

```mermaid
flowchart TD
    User["Human Operator / Analyst"] -->|HTTP / HTTPS| Frontend["Next.js Web Frontend"]
    User -->|Reviews & Approves Consequential Actions| Frontend

    Frontend -->|REST APIs & SSE Streams| API["FastAPI Gateway"]
    API -->|Persists Runs, Events, Evidence| DB[("PostgreSQL Database")]
    API -->|Enqueues Task Messages| Broker[("Redis Broker")]

    Broker -->|Pulls Work Orders| Worker["Celery Background Worker"]
    Worker -->|Executes State Graph| Engine["LangGraph Runtime"]

    Engine -->|State Checkpoints| DB
    Engine -->|Invokes Allowlisted Tools| ToolBox["Guarded Tool Sandbox"]
    Engine -->|Requests Plan & Synthesis| ModelAdapt["LLM Provider Adapter"]

    ToolBox -->|SSRF-Filtered HTTP| Web["Public Web / Target Domains"]
    ToolBox -->|Searches Corpus| SearchAdapt["Search Provider Adapter"]

    ModelAdapt -->|Default| MockLLM["Deterministic Mock LLM"]
    ModelAdapt -.->|Optional| LiveLLM["OpenAI / Ollama"]

    SearchAdapt -->|Default| MockSearch["Deterministic Mock Search Corpus"]
    SearchAdapt -.->|Optional| LiveSearch["Tavily Search API"]

    API -.->|Notification Webhooks (HMAC)| N8N["n8n Automation Engine"]
    N8N -.->|Trigger Run Webhook| API
```

---

## 2. Container & Service Architecture

AgentOps is containerized using Docker Compose for local-first deployment. The architecture consists of six dedicated services:

```mermaid
flowchart LR
    subgraph Host["Host Machine (Loopback 127.0.0.1)"]
        Browser["Web Browser"]
    end

    subgraph Compose["Docker Compose Network: agentops-net"]
        subgraph Edge["Frontend Tier"]
            UI["frontend: Next.js (Port 3000)"]
        end

        subgraph APITier["Application API Tier"]
            Backend["backend-api: FastAPI (Port 8000)"]
        end

        subgraph WorkerTier["Worker Tier"]
            CeleryApp["backend-worker: Celery + LangGraph"]
        end

        subgraph DataTier["Data & Message Tier"]
            PostgresSvc[("postgres: PostgreSQL 16 (Port 5432)")]
            RedisSvc[("redis: Redis 7.2 (Port 6379)")]
        end

        subgraph AutomationTier["Edge Automation Tier"]
            N8NSvc["n8n: Community Edition (Port 5678)"]
        end
    end

    Browser -->|Port 3000| UI
    Browser -->|Port 8000| Backend
    UI -->|Internal Proxy / CORS| Backend
    Backend -->|Async SQLAlchemy / asyncpg| PostgresSvc
    Backend -->|Publish Task| RedisSvc
    CeleryApp -->|Consume Task| RedisSvc
    CeleryApp -->|State Checkpoints & Events| PostgresSvc
    Backend -.->|Webhook Notifications| N8NSvc
    N8NSvc -.->|Trigger Submissions| Backend
```

### 2.1 Service Responsibilities

| Container Service | Primary Responsibilities | Trust Boundary |
| :--- | :--- | :--- |
| **frontend** | Renders React/TypeScript UI, run inspector, evidence drawer, HITL approval prompt. | Untrusted client tier; executes in user browser. |
| **backend-api** | Input validation (Pydantic), authentication/authorization, run creation, approval tokens, REST API endpoints. | Trusted gateway; enforces boundary checks. |
| **backend-worker** | Executes Celery background tasks, coordinates LangGraph state machine, invokes allowlisted tools. | Trusted execution domain; enforces timeouts and budgets. |
| **postgres** | Stores relational domain entities (Runs, Plans, Steps, Events, Evidence, Reports, Approvals, LangGraph Checkpoints). | Single source of truth for all application state. |
| **redis** | In-memory message broker for Celery queues and task result caching. | Transient transport; holds no durable run state. |
| **n8n** | External notification dispatch (Slack, email) and incoming trigger workflows. | External automation edge; NOT a source of truth. |

---

## 3. Agent Execution Lifecycle

The lifecycle of a research run transitions through six deterministic states:

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Analyst
    participant API as FastAPI Gateway
    participant DB as PostgreSQL
    participant Redis as Redis Queue
    participant Worker as Celery Worker
    participant LG as LangGraph Coordinator
    participant Tool as Tool Sandbox

    User->>API: POST /api/v1/runs (objective, domain)
    API->>API: Validate request payload via Pydantic
    API->>DB: INSERT Run (status="QUEUED")
    API->>Redis: Enqueue Celery Task (agentops.execute_run)
    API-->>User: HTTP 201 Created (run_id)

    Worker->>Redis: Pull Task (run_id)
    Worker->>DB: UPDATE Run (status="PLANNING")
    Worker->>LG: Initialize StateGraph with run_id
    LG->>LG: Synthesize & Validate ExecutionPlan (<= 10 steps)
    LG->>DB: INSERT ExecutionPlan & PlanSteps
    LG->>DB: Save Checkpoint (Node: Planner)
    LG->>DB: UPDATE Run (status="RUNNING")

    loop For Each Step in Plan
        LG->>LG: Check if Step requires human approval
        alt Requires Human Approval
            LG->>DB: INSERT ApprovalRequest (status="PENDING", token)
            LG->>DB: UPDATE Run (status="AWAITING_APPROVAL")
            LG->>DB: Save Checkpoint (Graph Suspended)
            LG-->>Worker: Worker pauses execution task
            API-->>User: Notification: Approval Required
            User->>API: POST /api/v1/runs/{id}/approvals/{approval_id} (verdict="approved")
            API->>DB: UPDATE ApprovalRequest (status="APPROVED")
            API->>Redis: Enqueue Resume Task
            Worker->>DB: Load Checkpoint (Node: Resume)
            LG->>DB: UPDATE Run (status="RUNNING")
        end

        LG->>Tool: Execute allowlisted tool (e.g., fetch_document)
        Tool->>Tool: SSRF IP & domain validation
        Tool-->>LG: Sanitized tool result
        LG->>DB: INSERT EvidenceRecord (content_hash, URL, snippet)
        LG->>DB: APPEND RunEvent (TOOL_CALLED, STEP_COMPLETED)
        LG->>DB: Save Checkpoint (Step N)
    end

    LG->>LG: Synthesize Final Report with citations
    LG->>DB: INSERT FinalReport & UPDATE Run (status="COMPLETED")
    LG->>DB: APPEND RunEvent (RUN_COMPLETED)
    LG-->>Worker: Task Completed
    User->>API: GET /api/v1/runs/{run_id}/report
    API-->>User: Rendered Markdown Report with verified citations
```

---

## 4. Component Interaction & State Ownership

### 4.1 PostgreSQL as the Single Source of Truth
To prevent architectural drift and distributed split-brain scenarios:
- **All authoritative run state** resides in PostgreSQL.
- **LangGraph Checkpoints** are serialized directly to PostgreSQL (`checkpoints` and `checkpoint_blobs` tables) using the PostgreSQL checkpointer.
- **n8n is strictly forbidden from holding primary run state**. n8n communicates solely via standard REST API endpoints with HMAC authentication; it never connects directly to the database or modifies run records.

### 4.2 Redis & Celery Messaging Architecture
- **Redis** operates as a transient task broker. If Redis is restarted or flushed, no historical run data or evidence is lost; active tasks are safely recovered or re-queued from PostgreSQL records.
- Celery worker tasks are idempotent; before executing a step, the worker verifies the current step index against PostgreSQL.

---

## 5. Traceability & Context Propagation

Every operation is tagged with four correlation identifiers to guarantee end-to-end auditability:

| Identifier | Generation Point | Scope | Propagation Mechanism |
| :--- | :--- | :--- | :--- |
| `correlation_id` | API Gateway (Middleware) | Entire HTTP request / response lifecycle | HTTP header `X-Correlation-ID`, structured log context. |
| `trace_id` | OpenTelemetry Tracer | Distributed trace spanning API, Celery, and DB | W3C `traceparent` header propagated in HTTP and Celery task headers. |
| `run_id` | API Gateway | Unique identifier for the research run | Stored in DB, passed as primary argument to Celery tasks and LangGraph state. |
| `step_id` | LangGraph Planner Node | Identifies individual task within the execution plan | Tagged in every `ToolEvent`, `EvidenceRecord`, and log statement. |

---

## 6. Failure Modes & Recovery Architecture

```mermaid
flowchart TD
    Start([Task Execution Begins]) --> StepExec{Execute Step}

    StepExec -->|Success| SaveCP[Save Checkpoint to PostgreSQL]
    SaveCP --> NextStep{More Steps?}
    NextStep -->|Yes| StepExec
    NextStep -->|No| Complete([Run Completed])

    StepExec -->|Transient Error: Timeout / 504| RetryCheck{Retry Count < 2?}
    RetryCheck -->|Yes| Backoff[Exponential Backoff 1s / 2s]
    Backoff --> StepExec
    RetryCheck -->|No| IsEssential{Step Essential?}

    IsEssential -->|No: Non-critical data| Degrade[Log Warning & Omit Source]
    Degrade --> SaveCP

    IsEssential -->|Yes: Core task| MarkFail[Mark Step FAILED]
    MarkFail --> RunFail[Set Run Status FAILED]
    RunFail --> Alert[Dispatch Error Webhook]

    StepExec -->|Worker Process Killed / OOM| Crash([Worker Crash])
    Crash --> Restart[Worker Restarts via Docker]
    Restart --> InspectDB[Inspect Run Status in DB]
    InspectDB --> Resume[Load Last Checkpoint & Resume Step]
    Resume --> StepExec

    StepExec -->|Security Violation: SSRF / Unregistered Tool| SecError[Raise SecurityValidationError]
    SecError --> AbortSecurity[Mark Run FAILED_SECURITY_POLICY]
    AbortSecurity --> AuditLog[Write High-Priority Audit Log]
```

### 6.1 Failure Recovery Matrix

| Failure Mode | Detection Point | Automated Recovery Action | Human Escalation |
| :--- | :--- | :--- | :--- |
| **Worker Process Crash (SIGKILL / OOM)** | Celery heartbeat failure / Docker healthcheck | Worker restarts automatically; unacknowledged task is redelivered; state is resumed from last DB checkpoint. | Notified if retry count exceeds 2. |
| **Transient Tool Timeout (HTTP 504)** | Tool execution wrapper | Bounded retry with exponential backoff (max 2 retries, 1s/2s). | Logged as warning event. |
| **Permanent Tool Failure (HTTP 404/410)** | Tool execution wrapper | If non-critical, step is omitted and noted in report; if critical, run terminates gracefully. | Logged in final report disclaimer. |
| **SSRF / Security Attack** | `app.core.security` validator | Immediate hard abort; socket connection blocked; run transitions to `FAILED_SECURITY_POLICY`. | Security audit event logged; webhook alert dispatched. |
| **Operator Rejection at HITL Gate** | API approval endpoint | State graph aborts cleanly; remaining steps marked skipped; run transitions to `ABORTED_BY_OPERATOR`. | Handled by operator action. |
