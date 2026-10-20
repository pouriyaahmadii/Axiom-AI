# Non-Functional Requirements: AgentOps

This document defines the verifiable Non-Functional Requirements (NFRs) for AgentOps. Each requirement specifies measurable quality attributes, avoiding unscientific or unachievable claims (e.g., "100% secure", "zero hallucinations"). Every NFR includes a stable ID, MoSCoW priority, rationale, verification method, acceptance criteria, dependencies, and release target.

---

## 1. Security & Principle of Least Privilege

### NFR-SEC-01: SSRF Defense Boundary
- **Requirement ID**: `NFR-SEC-01`
- **Priority**: Must Have (MVP)
- **Description**: All outbound HTTP requests initiated by tools must validate hostnames and resolved IP addresses against blocked private, loopback, link-local, multicast, and cloud metadata ranges before opening a socket.
- **Rationale**: Prevents external manipulation of the agent to probe internal networks, local service ports, or cloud instance identity services (`169.254.169.254`).
- **Verification Method**: Automated security unit test suite (`test_baseline.py`, `test_security.py`) attempting connections to `127.0.0.1`, `10.0.0.1`, `192.168.1.1`, `169.254.169.254`, and `localhost`.
- **Acceptance Criteria**:
  - 100% of test requests targeting blocked IP ranges or local hostnames are rejected with `SecurityValidationError`.
- **Dependencies**: `app.core.security`.
- **Release**: MVP

### NFR-SEC-02: Zero Arbitrary Code or Shell Execution
- **Requirement ID**: `NFR-SEC-02`
- **Priority**: Must Have (MVP)
- **Description**: The agent runtime must not include any tool, endpoint, or execution pathway that evaluates arbitrary shell commands (`bash`, `sh`), arbitrary SQL statements, or dynamic language evaluation (`eval`, `exec`).
- **Rationale**: Eliminates remote code execution (RCE) vulnerabilities stemming from prompt injection or model misalignment.
- **Verification Method**: Automated static analysis using `bandit` and code review confirming zero invocations of `os.system`, `subprocess`, `eval`, or unsanitized raw SQL queries.
- **Acceptance Criteria**:
  - Static security scan reports 0 High/Medium severity RCE issues.
- **Dependencies**: Architecture rules.
- **Release**: MVP

### NFR-SEC-03: Local Loopback Binding in Development
- **Requirement ID**: `NFR-SEC-03`
- **Priority**: Must Have (MVP)
- **Description**: All local services (FastAPI, PostgreSQL, Redis) must bind strictly to the loopback interface (`127.0.0.1`) by default. No service ports may listen on `0.0.0.0` unless explicitly configured for container networking.
- **Rationale**: Prevents accidental exposure of development databases or APIs to the local area network (LAN) or public interfaces.
- **Verification Method**: `netstat` or `lsof` socket audit during local execution.
- **Acceptance Criteria**:
  - Open listening sockets are restricted to `127.0.0.1` in development mode.
- **Dependencies**: `app.core.config`, `docker-compose.yml`.
- **Release**: MVP

---

## 2. Reliability & Recoverability

### NFR-REL-01: Crash Recovery via State Checkpoints
- **Requirement ID**: `NFR-REL-01`
- **Priority**: Must Have (MVP)
- **Description**: If a background Celery worker terminates abruptly during a run, the system must allow the run to be resumed from the last persisted LangGraph checkpoint without re-executing completed steps.
- **Rationale**: Prevents costly or duplicate tool execution when transient worker or infrastructure restarts occur.
- **Verification Method**: Chaos testing by killing a worker process midway through a multi-step run and issuing a resume command.
- **Acceptance Criteria**:
  - Resumed run picks up from the exact unexecuted step; previously recorded evidence remains intact.
- **Dependencies**: PostgreSQL checkpointing (`FR-STATE-01`).
- **Release**: MVP

### NFR-REL-02: Graceful Degradation on Non-Critical Tool Failure
- **Requirement ID**: `NFR-REL-02`
- **Priority**: Should Have (MVP)
- **Description**: When an external search or fetch tool fails after `MAX_RETRIES_PER_STEP`, the coordinator must not crash the entire process; it must record the error event and proceed to synthesis with available evidence.
- **Rationale**: Ensures the user receives a partial, useful analysis rather than an unhandled system exception.
- **Verification Method**: Unit test injecting an unrecoverable HTTP 500 error into a single competitor search step.
- **Acceptance Criteria**:
  - Run reaches status `COMPLETED_WITH_WARNINGS` and the final report explicitly notes data collection limitations.
- **Dependencies**: `FR-RESIL-01`, `FR-RESIL-03`.
- **Release**: MVP

---

## 3. Performance & Latency Budgets

### NFR-PERF-01: API Gateway Latency (P95 < 50ms)
- **Requirement ID**: `NFR-PERF-01`
- **Priority**: Must Have (MVP)
- **Description**: Under normal local development conditions, 95% of read requests (`GET /api/v1/health`, `GET /api/v1/runs/{id}`) must respond in less than 50 milliseconds.
- **Rationale**: Guarantees a snappy, responsive frontend dashboard without UI lag.
- **Verification Method**: Benchmark test using `pytest-benchmark` or `httpx` issuing 100 sequential status queries.
- **Acceptance Criteria**:
  - P95 response latency is verified < 50ms on local test environment.
- **Dependencies**: FastAPI, SQLAlchemy asyncpg driver.
- **Release**: MVP

### NFR-PERF-02: End-to-End Mock Run Duration (< 5.0s)
- **Requirement ID**: `NFR-PERF-02`
- **Priority**: Must Have (MVP)
- **Description**: A full 5-step competitor research run in deterministic Mock mode must complete from submission to report generation in under 5.0 seconds.
- **Rationale**: Enables high-velocity automated testing in CI/CD pipelines and provides instant demonstration turnaround for reviewers.
- **Verification Method**: Automated integration test measuring total wall-clock time of `test_mock_pipeline.py`.
- **Acceptance Criteria**:
  - Total elapsed time is < 5.0s on standard hardware.
- **Dependencies**: `FR-PROV-02`, Mock adapters.
- **Release**: MVP

---

## 4. Resource & Cost Governance

### NFR-BUD-01: Hard Dollar Cost Ceiling
- **Requirement ID**: `NFR-BUD-01`
- **Priority**: Must Have (MVP)
- **Description**: When utilizing live paid models (e.g., OpenAI), the coordinator must track estimated token usage and terminate execution if cumulative run cost exceeds `BUDGET_USD_LIMIT` (default: \$1.00).
- **Rationale**: Hard economic safeguard against runaway agent loops exhausting API balances.
- **Verification Method**: Unit test with a mock live provider accumulating token usage and verifying termination upon reaching budget ceiling.
- **Acceptance Criteria**:
  - Run transitions to `BUDGET_EXCEEDED` and halts subsequent tool calls when token cost exceeds limit.
- **Dependencies**: Cost calculation utility in `app.core`.
- **Release**: MVP

### NFR-BUD-02: Memory Footprint Bounds (< 1.5 GB Idle)
- **Requirement ID**: `NFR-BUD-02`
- **Priority**: Should Have (MVP)
- **Description**: The complete containerized local deployment (FastAPI, Redis, PostgreSQL, Celery, Next.js) must consume less than 1.5 GB of resident RAM when idle.
- **Rationale**: Ensures the platform can run comfortably on standard developer laptops without system starvation.
- **Verification Method**: Docker stats measurement after initial stack startup.
- **Acceptance Criteria**:
  - Sum of memory usage across all containers $\le 1.5$ GB.
- **Dependencies**: `docker-compose.yml`.
- **Release**: MVP

---

## 5. Accessibility & Responsive User Interface

### NFR-A11Y-01: Semantic HTML & WCAG 2.1 AA Target
- **Requirement ID**: `NFR-A11Y-01`
- **Priority**: Should Have (MVP)
- **Description**: The Next.js frontend UI must use semantic HTML tags, accessible form labels, visible focus states, and color contrast ratios meeting WCAG 2.1 AA targets (minimum 4.5:1 for normal text).
- **Rationale**: Ensures the operational dashboard is usable by keyboard-only users and screen readers.
- **Verification Method**: Automated accessibility auditing using axe-core or Playwright accessibility testing.
- **Acceptance Criteria**:
  - Zero critical or serious accessibility violations reported on primary dashboard pages.
- **Dependencies**: Next.js frontend, Tailwind CSS.
- **Release**: MVP

### NFR-A11Y-02: Responsive Viewport Adaptation
- **Requirement ID**: `NFR-A11Y-02`
- **Priority**: Should Have (MVP)
- **Description**: The dashboard UI must render cleanly without layout overflow or broken controls across viewports from 375px (mobile) to 1920px (desktop).
- **Rationale**: Allows operators to review runs and submit approvals from mobile devices or workstations.
- **Verification Method**: Responsive viewport testing in Playwright across mobile, tablet, and desktop dimensions.
- **Acceptance Criteria**:
  - No horizontal scrolling or overlapping elements on standard screen widths (375px, 768px, 1280px).
- **Dependencies**: Next.js frontend.
- **Release**: MVP

---

## 6. Maintainability & Code Quality

### NFR-MAINT-01: Modular Architecture & Separation of Concerns
- **Requirement ID**: `NFR-MAINT-01`
- **Priority**: Must Have (MVP)
- **Description**: Codebase must maintain strict layer separation: `api/` (HTTP/REST), `core/` (config/security), `domain/` (schemas/models), `orchestration/` (LangGraph), `adapters/` (external providers), and `db/` (persistence). No circular dependencies are permitted.
- **Rationale**: Facilitates unit testing, long-term code maintenance, and clean architectural review.
- **Verification Method**: Static import analysis and automated linting (`ruff check .`).
- **Acceptance Criteria**:
  - `ruff check .` passes with zero import errors or circular dependency warnings.
- **Dependencies**: Repository structure.
- **Release**: MVP

### NFR-MAINT-02: Strict Type Safety & Schema Validation
- **Requirement ID**: `NFR-MAINT-02`
- **Priority**: Must Have (MVP)
- **Description**: All domain entities, API request/response payloads, and tool contracts must use strict Pydantic v2 schemas. Type annotations must be present on all function signatures.
- **Rationale**: Eliminates runtime type errors and ensures deterministic boundary validation.
- **Verification Method**: `ruff check` with type annotations enabled and automated Pydantic schema validation tests.
- **Acceptance Criteria**:
  - 100% of API endpoints and tool interfaces have explicit type signatures and Pydantic models.
- **Dependencies**: Pydantic v2.
- **Release**: MVP

---

## 7. Local Developer Experience (DX)

### NFR-DX-01: Zero-Key Quickstart Under 5 Minutes
- **Requirement ID**: `NFR-DX-01`
- **Priority**: Must Have (MVP)
- **Description**: A developer must be able to clone the repository, set up a virtual environment, run the test suite, and start the local API in under 5 minutes without creating external API accounts.
- **Rationale**: Removes onboarding friction for technical evaluators and potential employers.
- **Verification Method**: Clean-slate setup walkthrough timed on a fresh checkout.
- **Acceptance Criteria**:
  - All unit tests pass and local API responds to `/api/v1/health` within 5 minutes of clone.
- **Dependencies**: `pyproject.toml`, `.env.example`, Mock mode.
- **Release**: MVP

### NFR-DX-02: Single-Command Verification Test Suite
- **Requirement ID**: `NFR-DX-02`
- **Priority**: Must Have (MVP)
- **Description**: The entire backend test suite must be runnable via a single standard command: `pytest backend/tests`.
- **Rationale**: Standardized, predictable developer ergonomics.
- **Verification Method**: Running `pytest backend/tests` in terminal sandbox.
- **Acceptance Criteria**:
  - 100% of baseline and unit tests execute cleanly with a passing exit code (0).
- **Dependencies**: Pytest, baseline test suite.
- **Release**: MVP

---

## 8. Observability & Auditability

### NFR-OBS-01: Structured JSON Logging
- **Requirement ID**: `NFR-OBS-01`
- **Priority**: Must Have (MVP)
- **Description**: All application log entries in production mode must be formatted as single-line JSON objects including `timestamp`, `level`, `logger`, `message`, `run_id`, and `step_id`.
- **Rationale**: Enables structured ingestion, searching, and filtering in modern log management systems (Datadog, Grafana Loki, CloudWatch).
- **Verification Method**: Test asserting JSON structure and required keys in captured log outputs.
- **Acceptance Criteria**:
  - `json.loads(log_line)` parses successfully and contains all mandatory context fields.
- **Dependencies**: `app.core.logging`.
- **Release**: MVP

### NFR-OBS-02: OpenTelemetry Trace Context Propagation
- **Requirement ID**: `NFR-OBS-02`
- **Priority**: Should Have (MVP)
- **Description**: When `OTEL_ENABLED=true`, the API gateway and Celery workers must propagate W3C Trace Context headers across HTTP requests and Celery tasks, binding operations to a unified trace ID.
- **Rationale**: Provides distributed end-to-end tracing across async job queues.
- **Verification Method**: Test checking for `traceparent` context extraction in worker tasks.
- **Acceptance Criteria**:
  - Distributed trace IDs are preserved across the API-to-worker boundary.
- **Dependencies**: OpenTelemetry SDK.
- **Release**: MVP

---

## 9. Reproducibility & Determinism

### NFR-REPRO-01: Seeded Deterministic Mock Behavior
- **Requirement ID**: `NFR-REPRO-01`
- **Priority**: Must Have (MVP)
- **Description**: Given an identical research objective and identical `MOCK_DETERMINISTIC_SEED`, the mock provider must generate bit-for-bit identical plans, tool arguments, and report outputs across runs.
- **Rationale**: Essential for deterministic regression testing and benchmark verification.
- **Verification Method**: Automated test running two independent mock pipelines with identical seeds and comparing SHA-256 hashes of the resulting reports.
- **Acceptance Criteria**:
  - Report hash match is 100% across identical seeded executions.
- **Dependencies**: `FR-PROV-02`.
- **Release**: MVP

---

## 10. Documentation Quality

### NFR-DOC-01: Professional English & Cross-Linking Integrity
- **Requirement ID**: `NFR-DOC-01`
- **Priority**: Must Have (MVP)
- **Description**: All repository documentation, comments, schemas, and API naming must be written in professional English with zero broken relative or markdown links.
- **Rationale**: Adheres to senior engineering portfolio presentation standards.
- **Verification Method**: Markdown link checking script verifying that all cross-document links resolve to existing files.
- **Acceptance Criteria**:
  - 100% of internal documentation links resolve correctly.
- **Dependencies**: `docs/` catalog.
- **Release**: MVP

---

## 11. Dependency & License Compliance

### NFR-LIC-01: Permissive Open-Source Licensing
- **Requirement ID**: `NFR-LIC-01`
- **Priority**: Must Have (MVP)
- **Description**: AgentOps and all direct third-party Python/Node libraries must use permissive open-source licenses (MIT, Apache-2.0, BSD). No copyleft (GPL/AGPL) dependencies are permitted in the core application codebase.
- **Rationale**: Prevents license taint and ensures legal freedom for portfolio evaluation and commercial adoption.
- **Verification Method**: Automated license audit using `pip-licenses`.
- **Acceptance Criteria**:
  - 0 GPL/AGPL dependencies detected in runtime dependency graph.
- **Dependencies**: `pyproject.toml`.
- **Release**: MVP
