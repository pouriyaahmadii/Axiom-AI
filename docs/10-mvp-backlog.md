# MVP Engineering Backlog & Phased Roadmap: AgentOps

## 1. Backlog Prioritization Methodology (MoSCoW)

This backlog organizes engineering tasks for the AgentOps platform into four disciplined priority tiers:
- **Must Have (M)**: Mandatory for MVP demonstration, security, and verification. Without these, the product cannot be validated.
- **Should Have (S)**: Important capabilities that increase operational resilience and user experience, but have viable workarounds if delayed.
- **Could Have (C)**: Desirable enhancements included only if MVP schedule permits.
- **Won't Have (W - Deliberately Deferred)**: Explicitly out of scope for the MVP to prevent scope creep.

---

## 2. Epics & Task Breakdown

### Epic 1: Project Foundation, Baseline & Security Architecture
*Status: COMPLETED (Phase 1)*
- [x] **TASK-101 (M)**: Create `.gitignore`, `.env.example`, and directory structure (`backend/`, `frontend/`, `docker/`, `docs/`).
- [x] **TASK-102 (M)**: Configure `pyproject.toml` with Ruff, Pytest, FastAPI, Pydantic, Celery, and LangGraph.
- [x] **TASK-103 (M)**: Implement SSRF defense library (`app.core.security.is_safe_url`) blocking private IPs, loopback, and cloud metadata (169.254.169.254).
- [x] **TASK-104 (M)**: Implement structured JSON logging (`app.core.logging`) and environment settings (`app.core.config`).
- [x] **TASK-105 (M)**: Create baseline test suite (`test_baseline.py`) verifying security primitives and API readiness (12/12 passing).
- [x] **TASK-106 (M)**: Author foundational project documentation (`00-product-vision.md` through `04-glossary.md`).

---

### Epic 2: Domain Schemas, State Store & Database Layer
*Priority: Must Have (Next Phase)*
- [ ] **TASK-201 (M)**: Define strict Pydantic v2 domain schemas (`RunRequest`, `ExecutionPlan`, `PlanStep`, `ToolEvent`, `EvidenceRecord`, `ApprovalRequest`, `FinalReport`).
- [ ] **TASK-202 (M)**: Implement SQLAlchemy 2.0 async declarative models for PostgreSQL persistence.
- [ ] **TASK-203 (M)**: Configure Alembic migrations for initial schema creation.
- [ ] **TASK-204 (M)**: Implement repository layer for state persistence, event logging, and checkpointing.
- [ ] **TASK-205 (M)**: Write unit test suite for schema validation, edge cases, and serialization.

---

### Epic 3: Provider Adapter Layer & Deterministic Mock Engine
*Priority: Must Have*
- [ ] **TASK-301 (M)**: Define abstract base interfaces `BaseLLMAdapter` and `BaseSearchAdapter`.
- [ ] **TASK-302 (M)**: Implement `MockLLMAdapter` producing deterministic, seeded planning and report synthesis.
- [ ] **TASK-303 (M)**: Implement `MockSearchAdapter` querying a pre-packaged competitor intelligence corpus (`competitor_corpus.json`).
- [ ] **TASK-304 (S)**: Implement optional live adapters for OpenAI-compatible models, local Ollama, and Tavily search.
- [ ] **TASK-305 (M)**: Write unit tests verifying bit-for-bit reproducibility of mock outputs.

---

### Epic 4: LangGraph Orchestrator & Safe Tool Sandbox
*Priority: Must Have*
- [ ] **TASK-401 (M)**: Implement LangGraph StateGraph coordinator (Plan -> Validate -> Step Execution Loop -> HITL Pause/Resume -> Evidence -> Synthesize).
- [ ] **TASK-402 (M)**: Implement Tool Registry with allowlist enforcement (`web_search`, `fetch_document`, `extract_metrics`).
- [ ] **TASK-403 (M)**: Integrate SSRF guard and response size limits into `fetch_document`.
- [ ] **TASK-404 (M)**: Implement Human-in-the-Loop interrupt and resume checkpoint mechanics in LangGraph.
- [ ] **TASK-405 (M)**: Implement citation grounding auditor ensuring every empirical assertion links to a valid `EvidenceRecord`.
- [ ] **TASK-406 (M)**: Enforce global timeout, per-step timeout, and bounded retry handlers.

---

### Epic 5: FastAPI Backend API & Celery Background Queue
*Priority: Must Have*
- [ ] **TASK-501 (M)**: Implement REST endpoints:
  - `POST /api/v1/runs` (submit objective)
  - `GET /api/v1/runs/{id}` (inspect status, plan, events)
  - `POST /api/v1/runs/{id}/cancel` (cancel run)
  - `POST /api/v1/runs/{id}/approvals/{approval_id}` (submit approval verdict)
  - `GET /api/v1/runs/{id}/report` (retrieve report with citations)
- [ ] **TASK-502 (M)**: Configure Celery task worker executing LangGraph state graphs off the main thread.
- [ ] **TASK-503 (M)**: Integrate Redis broker and result backend.
- [ ] **TASK-504 (S)**: Add OpenTelemetry tracing instrumentation to API routes and worker tasks.
- [ ] **TASK-505 (M)**: Write integration test suite covering the complete API and background task lifecycle.

---

### Epic 6: Containerization & Self-Hosted Stack
*Priority: Must Have*
- [ ] **TASK-601 (M)**: Author multi-stage Dockerfile for backend (FastAPI + Celery).
- [ ] **TASK-602 (M)**: Author Dockerfile for frontend (Next.js standalone build).
- [ ] **TASK-603 (M)**: Author `docker-compose.yml` orchestrating PostgreSQL, Redis, API, Worker, n8n, and Frontend.
- [ ] **TASK-604 (M)**: Enforce loopback bindings (`127.0.0.1`) and healthcheck dependencies.

---

### Epic 7: Operations Dashboard Frontend (Next.js, TypeScript)
*Priority: Must Have*
- [ ] **TASK-701 (M)**: Initialize Next.js App Router project with TypeScript and Tailwind CSS.
- [ ] **TASK-702 (M)**: Build Run Submission page with provider selector (Mock / Live) and constraint inputs.
- [ ] **TASK-703 (M)**: Build Live Execution Inspector displaying the plan DAG, active step, and event timeline.
- [ ] **TASK-704 (M)**: Build interactive Human Approval Gate modal allowing one-click review and verdict submission.
- [ ] **TASK-705 (M)**: Build Markdown Report Viewer with interactive citation drawer displaying source snippets.
- [ ] **TASK-706 (S)**: Playwright end-to-end UI verification tests.

---

### Epic 8: n8n Automation & Webhook Integration
*Priority: Should Have*
- [ ] **TASK-801 (S)**: Author n8n workflow template listening for external triggers and initiating AgentOps runs.
- [ ] **TASK-802 (S)**: Author n8n workflow template receiving AgentOps notification webhooks (approval required, run completed).
- [ ] **TASK-803 (M)**: Implement HMAC-SHA256 signature verification on all webhook payloads.

---

### Epic 9: End-to-End Verification, Security Audit & CI/CD
*Priority: Must Have*
- [ ] **TASK-901 (M)**: Configure GitHub Actions CI workflow executing `ruff check`, `ruff format --check`, and `pytest backend/tests`.
- [ ] **TASK-902 (M)**: Run automated security audit with `bandit` and license compliance check.
- [ ] **TASK-903 (M)**: Conduct end-to-end rehearsal of the competitor intelligence demo and update final documentation.

---

## 3. Deliberately Deferred Features (Won't Have in MVP)

The following capabilities are explicitly deferred to post-MVP milestones to maintain architectural focus and avoid premature complexity:

| Feature | Justification for Deferral | Target Milestone |
| :--- | :--- | :--- |
| **Multi-Tenant SaaS & Auth** | AgentOps is designed as a single-operator or team-shared self-hosted platform; multi-tenant auth and Stripe billing add non-core complexity. | Milestone 2 |
| **Dynamic Multi-Agent Swarms** | Unrestricted agent swarms are non-deterministic and difficult to audit; single-coordinator architecture is safer and more reliable. | Milestone 2 |
| **Arbitrary Code Execution Sandbox** | Sandboxing dynamic Python execution introduces severe security attack surfaces not required for structured research tasks. | Milestone 2 |
| **Aggressive Web Crawling** | Bypassing CAPTCHAs and scraping bot-protected sites violates ethical standards and legal boundaries; public permitted sources suffice. | Milestone 2 |
| **Dedicated Vector Database** | A dedicated vector cluster (Pinecone/Qdrant) introduces operational overhead; relational storage with exact citations satisfies MVP grounding. | Milestone 2 |
| **Native Mobile Apps** | Responsive web dashboard via Next.js provides full mobile usability without maintaining separate iOS/Android codebases. | Milestone 3 |
