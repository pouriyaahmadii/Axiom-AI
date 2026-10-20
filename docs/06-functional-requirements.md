# Functional Requirements: AgentOps

This document details all testable functional requirements for AgentOps. Each requirement is assigned a stable identifier, MoSCoW priority, explicit rationale, verification method, acceptance criteria, dependencies, and target release milestone.

---

## 1. Run Creation & Ingestion

### FR-RUN-01: Research Run Submission & Validation
- **Requirement ID**: `FR-RUN-01`
- **Priority**: Must Have (MVP)
- **Description**: The API must provide an endpoint `POST /api/v1/runs` accepting a research request. The payload must include `objective` (string, 10–2000 chars), `domain` (string), `geography` (optional string), `constraints` (optional object), and `provider_override` (optional).
- **Rationale**: Establishes a validated, uniform entry point for analytical research objectives while rejecting malformed or excessively long inputs at the API gateway.
- **Verification Method**: Automated integration test using `httpx.AsyncClient` submitting valid payloads, empty payloads, and boundary-violating payloads.
- **Acceptance Criteria**:
  - Valid submission returns HTTP 201 with `{"run_id": "...", "status": "QUEUED", "created_at": "..."}`.
  - Payloads violating length or schema constraints return HTTP 422 with structured validation errors.
- **Dependencies**: Database models (`app.db`), Pydantic schemas (`app.domain`).
- **Release**: MVP

### FR-RUN-02: Run State Initialization & Enqueueing
- **Requirement ID**: `FR-RUN-02`
- **Priority**: Must Have (MVP)
- **Description**: Upon successful validation, the system must persist an initial `Run` record with status `QUEUED` in PostgreSQL and enqueue a background execution task via Celery and Redis.
- **Rationale**: Ensures durability against API crashes; no submitted request is lost before background worker pickup.
- **Verification Method**: Test validating PostgreSQL row creation and Celery task publication via Redis inspection.
- **Acceptance Criteria**:
  - Database contains a matching `Run` entity with status `QUEUED` within 50ms of API 201 response.
  - Celery broker receives task `agentops.execute_run` containing the exact `run_id`.
- **Dependencies**: `FR-RUN-01`, Celery, Redis, PostgreSQL.
- **Release**: MVP

---

## 2. Execution Plan Generation

### FR-PLAN-01: Structured Plan Synthesis
- **Requirement ID**: `FR-PLAN-01`
- **Priority**: Must Have (MVP)
- **Description**: The coordinator must invoke the planning model to decompose the research objective into an `ExecutionPlan` comprising an ordered list of `PlanStep` entities.
- **Rationale**: Converts opaque text objectives into discrete, inspectable, and auditable units of work before tool invocation begins.
- **Verification Method**: Unit test invoking the planner node with Mock LLM and verifying output schema conformity.
- **Acceptance Criteria**:
  - Plan output matches the `ExecutionPlan` Pydantic schema.
  - Total steps `N` is constrained by $1 \le N \le \text{MAX\_PLAN\_STEPS}$ (default: 10).
  - Every step contains non-empty `step_id`, `title`, `tool_name`, `parameters`, and `requires_human_approval` boolean.
- **Dependencies**: `FR-RUN-02`, `FR-PROV-01`, LangGraph.
- **Release**: MVP

### FR-PLAN-02: Deterministic Mock Plan Output
- **Requirement ID**: `FR-PLAN-02`
- **Priority**: Must Have (MVP)
- **Description**: When configured with `LLM_PROVIDER=mock`, the planner must output a deterministic, repeatable competitor analysis plan for a given seed and objective.
- **Rationale**: Permits fully automated CI testing and portfolio evaluation without external API costs or non-deterministic test failures.
- **Verification Method**: Unit test asserting that 10 consecutive invocations with the same seed produce identical plan JSONs.
- **Acceptance Criteria**:
  - Output plan hashes are identical across identical test runs.
- **Dependencies**: `FR-PLAN-01`, `FR-PROV-02`.
- **Release**: MVP

---

## 3. Plan & Step Validation

### FR-VAL-01: Plan Validation & Tool Allowlist Verification
- **Requirement ID**: `FR-VAL-01`
- **Priority**: Must Have (MVP)
- **Description**: Before executing any step in the plan, the coordinator must validate that: (a) all referenced `tool_name` values exist in the active Tool Registry, (b) total steps $\le \text{MAX\_PLAN\_STEPS}$, and (c) step dependency graphs contain no cycles.
- **Rationale**: Prevents LLMs from inventing non-existent tools, triggering execution loops, or exceeding resource allocations.
- **Verification Method**: Unit test passing plans with valid tools, unknown tools, cycles, and >10 steps to the validator.
- **Acceptance Criteria**:
  - Plans with unregistered tools or cyclic dependencies are rejected; run transitions to `FAILED` with an explicit validation error event.
  - Valid plans transition run status to `PLAN_VALIDATED`.
- **Dependencies**: `FR-PLAN-01`, `FR-TOOL-01`.
- **Release**: MVP

### FR-VAL-02: Step Parameter Schema Conformance
- **Requirement ID**: `FR-VAL-02`
- **Priority**: Must Have (MVP)
- **Description**: Each step's `parameters` dictionary must be validated against the Pydantic input schema of the targeted tool prior to invocation.
- **Rationale**: Isolates tool execution from corrupted or malformed model parameters.
- **Verification Method**: Unit test attempting tool execution with invalid parameter keys and types.
- **Acceptance Criteria**:
  - Parameter mismatch raises a structured `ToolValidationError` without executing the underlying function.
- **Dependencies**: `FR-VAL-01`, `FR-TOOL-02`.
- **Release**: MVP

---

## 4. Bounded Task Execution

### FR-EXEC-01: Guarded Tool Invocation
- **Requirement ID**: `FR-EXEC-01`
- **Priority**: Must Have (MVP)
- **Description**: The execution engine must invoke approved tools sequentially or by resolved dependency order, injecting run context (`run_id`, `step_id`) and recording execution duration.
- **Rationale**: Guarantees strict traceability and prevents out-of-order execution.
- **Verification Method**: Integration test verifying execution sequence against step dependencies.
- **Acceptance Criteria**:
  - Tools are executed in topological dependency order.
  - Step transitions are logged with millisecond timestamps.
- **Dependencies**: `FR-VAL-01`, `FR-TOOL-01`.
- **Release**: MVP

### FR-EXEC-02: Global and Per-Step Timeout Enforcement
- **Requirement ID**: `FR-EXEC-02`
- **Priority**: Must Have (MVP)
- **Description**: Execution of any individual step must terminate if it exceeds `STEP_TIMEOUT_SECONDS` (default: 60s). The entire run must terminate if elapsed time exceeds `MAX_EXECUTION_SECONDS` (default: 300s).
- **Rationale**: Prevents hanging socket connections or stuck external requests from consuming worker threads indefinitely.
- **Verification Method**: Integration test with a mocked hanging tool verifying timeout interruption and error handling.
- **Acceptance Criteria**:
  - Step hanging beyond timeout is cancelled, raising `StepTimeoutError`.
  - Global timeout marks run as `TIMED_OUT` and halts subsequent step processing.
- **Dependencies**: `FR-EXEC-01`, Celery.
- **Release**: MVP

---

## 5. State Persistence & Checkpointing

### FR-STATE-01: Transactional Step State Checkpoints
- **Requirement ID**: `FR-STATE-01`
- **Priority**: Must Have (MVP)
- **Description**: The LangGraph state machine must persist its serialized state graph to PostgreSQL after each node execution, including current step index, completed step outputs, and accumulated evidence.
- **Rationale**: Enables reliable recovery from worker crashes and clean suspension during human approval gates.
- **Verification Method**: Test verifying PostgreSQL checkpoints table contains updated state after each step.
- **Acceptance Criteria**:
  - Database contains valid JSON state checkpoint corresponding to each executed step.
- **Dependencies**: LangGraph PostgreSQL checkpointer, PostgreSQL schema.
- **Release**: MVP

### FR-STATE-02: Immutable Event Sourcing Log
- **Requirement ID**: `FR-STATE-02`
- **Priority**: Must Have (MVP)
- **Description**: Every lifecycle event (`RUN_STARTED`, `PLAN_GENERATED`, `STEP_STARTED`, `TOOL_CALLED`, `APPROVAL_REQUESTED`, `STEP_COMPLETED`, `RUN_COMPLETED`) must be appended to an immutable `RunEvent` table with timestamp and event metadata.
- **Rationale**: Provides an audit trail for observability, operator debugging, and UI timeline rendering.
- **Verification Method**: Querying `RunEvent` table after a completed run to verify sequential order of events.
- **Acceptance Criteria**:
  - Events are strictly append-only; update/delete operations on `RunEvent` are rejected.
- **Dependencies**: `FR-RUN-02`, PostgreSQL.
- **Release**: MVP

---

## 6. Resilience, Retries, Cancellation & Recovery

### FR-RESIL-01: Bounded Step Retries
- **Requirement ID**: `FR-RESIL-01`
- **Priority**: Must Have (MVP)
- **Description**: When a tool execution encounters a transient failure (network timeout, rate limit), the step must be retried up to `MAX_RETRIES_PER_STEP` (default: 2) with exponential backoff before marking the step as failed.
- **Rationale**: Handles transient network glitches without failing the entire research job.
- **Verification Method**: Unit test simulating a tool failing on initial call and succeeding on retry.
- **Acceptance Criteria**:
  - Tool retries exactly up to configured maximum, logging a retry event for each attempt.
  - Failures exceeding maximum retries transition step to `FAILED`.
- **Dependencies**: `FR-EXEC-01`.
- **Release**: MVP

### FR-RESIL-02: Run Cancellation
- **Requirement ID**: `FR-RESIL-02`
- **Priority**: Must Have (MVP)
- **Description**: An operator must be able to cancel an active run via `POST /api/v1/runs/{run_id}/cancel`. The worker must abort subsequent steps and mark run status as `CANCELLED`.
- **Rationale**: Allows operators to stop runaway tasks or unwanted queries immediately.
- **Verification Method**: API test submitting cancel request while a multi-step run is executing.
- **Acceptance Criteria**:
  - Run status immediately transitions to `CANCELLED`; in-flight Celery task is revoked.
- **Dependencies**: `FR-RUN-02`, Celery task control.
- **Release**: MVP

### FR-RESIL-03: Partial Completion & Graceful Degradation
- **Requirement ID**: `FR-RESIL-03`
- **Priority**: Should Have (MVP)
- **Description**: If a non-essential research step fails after retries, the coordinator must record the failure and attempt report synthesis with available evidence rather than failing the entire run, noting omitted sections in the report.
- **Rationale**: Yields useful partial analytical output even when a single source fails to respond.
- **Verification Method**: Integration test with one failing non-critical competitor query verifying successful report synthesis noting partial data.
- **Acceptance Criteria**:
  - Run status is marked `COMPLETED_WITH_WARNINGS`; final report notes the missing data source.
- **Dependencies**: `FR-RESIL-01`, `FR-REP-01`.
- **Release**: MVP

---

## 7. Model & Search Provider Adapters

### FR-PROV-01: Pluggable Provider Adapter Architecture
- **Requirement ID**: `FR-PROV-01`
- **Priority**: Must Have (MVP)
- **Description**: The system must define abstract base interfaces `BaseLLMAdapter` and `BaseSearchAdapter`. Application code must depend strictly on these interfaces, not provider-specific SDKs.
- **Rationale**: Decouples application logic from specific AI vendors and prevents hardcoded dependencies.
- **Verification Method**: Code architecture audit and interface compliance unit tests.
- **Acceptance Criteria**:
  - Adapters adhere to defined abstract methods for plan generation, tool calling, and text synthesis.
- **Dependencies**: Core architecture.
- **Release**: MVP

### FR-PROV-02: Deterministic Mock Provider Implementations
- **Requirement ID**: `FR-PROV-02`
- **Priority**: Must Have (MVP)
- **Description**: The platform must supply `MockLLMAdapter` and `MockSearchAdapter` that operate fully offline, producing deterministic schema-valid responses based on a canned research dataset.
- **Rationale**: Guarantees zero-cost, hermetic testing and seamless evaluation for recruiters and evaluators.
- **Verification Method**: End-to-end integration test executed with no internet connectivity and no API keys.
- **Acceptance Criteria**:
  - Test suite passes 100% offline with zero outbound network calls.
- **Dependencies**: `FR-PROV-01`.
- **Release**: MVP

### FR-PROV-03: Optional Live Provider Adapters
- **Requirement ID**: `FR-PROV-03`
- **Priority**: Should Have (MVP)
- **Description**: The platform must support optional drop-in adapters for: (a) OpenAI-compatible APIs (GPT-4o/mini), (b) local Ollama instances, and (c) Tavily search, configured via `.env`.
- **Rationale**: Allows users with API keys or local LLMs to run live research runs without modifying code.
- **Verification Method**: Unit test verifying adapter initialization when environment variables are supplied.
- **Acceptance Criteria**:
  - Supplying valid keys enables live provider routing without affecting mock defaults.
- **Dependencies**: `FR-PROV-01`.
- **Release**: MVP

---

## 8. Tool Registry & Sandboxing

### FR-TOOL-01: Tool Allowlist Registry
- **Requirement ID**: `FR-TOOL-01`
- **Priority**: Must Have (MVP)
- **Description**: The system must maintain an immutable registry of approved tools: `web_search`, `fetch_document`, and `extract_metrics`. Any attempt to register or execute an unapproved tool must raise a security exception.
- **Rationale**: Core security defense preventing arbitrary code, shell, or file evaluation.
- **Verification Method**: Unit test attempting to invoke an unregistered tool name.
- **Acceptance Criteria**:
  - Unregistered tool invocation immediately raises `SecurityValidationError` and halts step execution.
- **Dependencies**: `app.core.security`.
- **Release**: MVP

### FR-TOOL-02: SSRF-Guarded HTTP Document Fetching
- **Requirement ID**: `FR-TOOL-02`
- **Priority**: Must Have (MVP)
- **Description**: The `fetch_document` tool must validate the target URL using `app.core.security.is_safe_url`. Requests targeting loopback, private subnets (RFC 1918), link-local addresses, or cloud metadata IP (`169.254.169.254`) must be rejected.
- **Rationale**: Prevents the agent from scanning internal network environments or exfiltrating cloud credentials.
- **Verification Method**: Unit test suite passing internal IP addresses and hostnames to the fetch tool.
- **Acceptance Criteria**:
  - All private/loopback/metadata URLs return a security rejection and log a security violation event.
- **Dependencies**: `FR-TOOL-01`, `app.core.security`.
- **Release**: MVP

---

## 9. Evidence Provenance & Citation Grounding

### FR-EVID-01: Immutable Evidence Recording
- **Requirement ID**: `FR-EVID-01`
- **Priority**: Must Have (MVP)
- **Description**: Every tool response containing factual data must generate an `EvidenceRecord` storing `run_id`, `source_url`, `content_hash` (SHA-256), `raw_snippet`, and `retrieval_timestamp`.
- **Rationale**: Establishes cryptographic provenance for all data later used in the final report.
- **Verification Method**: Database inspection after tool execution verifying `EvidenceRecord` row insertion.
- **Acceptance Criteria**:
  - Stored `content_hash` matches the SHA-256 calculation of the `raw_snippet`.
- **Dependencies**: `FR-EXEC-01`, PostgreSQL schema.
- **Release**: MVP

### FR-EVID-02: Citation Linking in Report Synthesis
- **Requirement ID**: `FR-EVID-02`
- **Priority**: Must Have (MVP)
- **Description**: The synthesizer prompt and schema must require that any factual assertion in the final report include an explicit markdown citation anchor (e.g., `[^ev-1]`) linking to a specific `evidence_id`.
- **Rationale**: Prevents ungrounded model hallucinations from passing into the final deliverable.
- **Verification Method**: Automated citation auditor validating that every cited ID exists in the run's `EvidenceRecord` table.
- **Acceptance Criteria**:
  - 100% of citations in the report resolve to valid evidence records for that run.
- **Dependencies**: `FR-EVID-01`, `FR-REP-01`.
- **Release**: MVP

---

## 10. Report Generation & Factual Verification

### FR-REP-01: Structured Markdown Report Synthesis
- **Requirement ID**: `FR-REP-01`
- **Priority**: Must Have (MVP)
- **Description**: The synthesizer must generate a structured Markdown report containing: Executive Summary, Competitor Comparison Matrix (Products, Pricing, Positioning), Evidence-Backed Findings, and a Bibliography of Citations.
- **Rationale**: Produces a standardized, professional deliverable for analysts and evaluators.
- **Verification Method**: Schema and AST validation of generated report markdown.
- **Acceptance Criteria**:
  - Report conforms to standard markdown headings and includes all required analytical sections.
- **Dependencies**: `FR-EVID-02`, `FR-PROV-01`.
- **Release**: MVP

### FR-REP-02: Evidence vs. Inference Separation
- **Requirement ID**: `FR-REP-02`
- **Priority**: Must Have (MVP)
- **Description**: The final report must structurally separate empirical evidence from model inference using dedicated headings: `## Empirical Findings (Grounded Evidence)` and `## Strategic Inferences & Analysis`.
- **Rationale**: Clear epistemic hygiene ensuring readers know which statements are documented facts and which are AI interpretations.
- **Verification Method**: Markdown AST parsing verifying the presence of distinct sections.
- **Acceptance Criteria**:
  - Both sections are present; no ungrounded claims appear in the empirical findings section.
- **Dependencies**: `FR-REP-01`.
- **Release**: MVP

---

## 11. Human-in-the-Loop (HITL) Approval

### FR-HITL-01: Consequential Action Pause & Token Generation
- **Requirement ID**: `FR-HITL-01`
- **Priority**: Must Have (MVP)
- **Description**: When a plan step with `requires_human_approval = True` is reached, the state graph must pause execution, transition run status to `AWAITING_APPROVAL`, generate a secure random approval token, and persist an `ApprovalRequest` entity.
- **Rationale**: Enforces human oversight before taking consequential actions (e.g., external publication, sending emails).
- **Verification Method**: Integration test with an approval-gated step verifying orchestrator pause and token generation.
- **Acceptance Criteria**:
  - State graph pauses; background worker releases task; run status is `AWAITING_APPROVAL`.
- **Dependencies**: `FR-STATE-01`, `app.core.security`.
- **Release**: MVP

### FR-HITL-02: Approval & Rejection Endpoint Handling
- **Requirement ID**: `FR-HITL-02`
- **Priority**: Must Have (MVP)
- **Description**: The API must provide `POST /api/v1/runs/{run_id}/approvals/{approval_id}` accepting `{"verdict": "approved" | "rejected", "operator_notes": "..."}`.
- **Rationale**: Provides an authenticated interface for operators to control paused runs.
- **Verification Method**: API test submitting approval and rejection verdicts.
- **Acceptance Criteria**:
  - `approved` updates status to `APPROVED` and dispatches Celery resume task.
  - `rejected` marks run as `ABORTED_BY_OPERATOR` and terminates execution cleanly.
- **Dependencies**: `FR-HITL-01`.
- **Release**: MVP

---

## 12. n8n Automation & Webhook Integration

### FR-N8N-01: Outbound Notification Webhook Dispatch
- **Requirement ID**: `FR-N8N-01`
- **Priority**: Must Have (MVP)
- **Description**: When an approval is required or a run reaches a terminal state (`COMPLETED`, `FAILED`), AgentOps must dispatch an HTTP POST webhook to the configured `N8N_WEBHOOK_URL` containing run status, event summary, and approval link.
- **Rationale**: Enables external automated alerting (Slack, email) via n8n without embedding notification logic in the backend.
- **Verification Method**: Integration test with a mock HTTP webhook receiver verifying payload and headers.
- **Acceptance Criteria**:
  - Webhook is dispatched within 500ms of state transition.
- **Dependencies**: `FR-HITL-01`, `FR-STATE-02`.
- **Release**: MVP

### FR-N8N-02: HMAC Webhook Signature Verification
- **Requirement ID**: `FR-N8N-02`
- **Priority**: Must Have (MVP)
- **Description**: Inbound and outbound webhook payloads must include an `X-AgentOps-Signature` header calculated using HMAC-SHA256 with `N8N_WEBHOOK_SECRET`.
- **Rationale**: Prevents webhook spoofing or unauthorized triggers from untrusted sources.
- **Verification Method**: Test verifying rejection of payloads with invalid signatures using constant-time comparison.
- **Acceptance Criteria**:
  - Requests with invalid signatures return HTTP 401 Unauthorized.
- **Dependencies**: `app.core.security.verify_hmac_signature`.
- **Release**: MVP

---

## 13. Operations Dashboard & Frontend UI

### FR-UI-01: Interactive Run Submission View
- **Requirement ID**: `FR-UI-01`
- **Priority**: Must Have (MVP)
- **Description**: The Next.js frontend must provide a clean form allowing users to submit research objectives, choose provider mode (`mock` or `live`), set constraints, and trigger execution.
- **Rationale**: Core user interface for researchers and evaluators to interact with the platform.
- **Verification Method**: Playwright E2E UI test submitting a research run.
- **Acceptance Criteria**:
  - Form submission triggers `POST /api/v1/runs` and redirects to the active run dashboard.
- **Dependencies**: `FR-RUN-01`, Next.js app.
- **Release**: MVP

### FR-UI-02: Live Execution Plan & Timeline Inspector
- **Requirement ID**: `FR-UI-02`
- **Priority**: Must Have (MVP)
- **Description**: The run view must display the generated execution plan DAG, current active step, step statuses (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`), and real-time execution logs.
- **Rationale**: Complete operational transparency during run execution.
- **Verification Method**: UI inspection and Playwright verification of state transitions.
- **Acceptance Criteria**:
  - Visual status updates in real time as events occur.
- **Dependencies**: `FR-STATE-02`, `FR-UI-01`.
- **Release**: MVP

### FR-UI-03: Interactive Human Approval Gate Modal
- **Requirement ID**: `FR-UI-03`
- **Priority**: Must Have (MVP)
- **Description**: When a run enters `AWAITING_APPROVAL`, the UI must display a prominent approval banner/modal showing proposed action parameters and allowing the operator to click "Approve" or "Reject".
- **Rationale**: Intuitive interface for human-in-the-loop oversight.
- **Verification Method**: Playwright test simulating approval click and verifying run resumption.
- **Acceptance Criteria**:
  - Clicking "Approve" triggers the approval API and updates UI status to resuming.
- **Dependencies**: `FR-HITL-02`, `FR-UI-02`.
- **Release**: MVP

### FR-UI-04: Report Viewer with Citation Backlinks
- **Requirement ID**: `FR-UI-04`
- **Priority**: Must Have (MVP)
- **Description**: Completed runs must render the synthesized report in rich Markdown, where clicking any citation anchor opens an evidence drawer showing the exact raw text snippet and source URL.
- **Rationale**: Makes report verification effortless and immediate.
- **Verification Method**: Playwright test clicking citation anchor and asserting evidence drawer visibility.
- **Acceptance Criteria**:
  - Citation clicks smoothly open the evidence inspector with matching snippet and URL.
- **Dependencies**: `FR-REP-01`, `FR-EVID-01`.
- **Release**: MVP

---

## 14. Evaluation Datasets & Repeatable Testing

### FR-EVAL-01: Standardized Competitor Benchmark Dataset
- **Requirement ID**: `FR-EVAL-01`
- **Priority**: Must Have (MVP)
- **Description**: The repository must contain a standardized competitor research evaluation dataset (`tests/fixtures/competitor_corpus.json`) covering 3 representative companies with pricing, features, and announcements.
- **Rationale**: Enables deterministic, repeatable offline benchmarking without web access.
- **Verification Method**: Test asserting fixture presence, valid JSON structure, and complete field population.
- **Acceptance Criteria**:
  - Fixture file is checked into git and conforms to the `CompetitorProfile` schema.
- **Dependencies**: Test suite setup.
- **Release**: MVP

### FR-EVAL-02: Automated End-to-End Replay Suite
- **Requirement ID**: `FR-EVAL-02`
- **Priority**: Must Have (MVP)
- **Description**: The test suite must include an automated end-to-end replay test that runs a complete competitor research workflow from API submission to report validation in Mock mode.
- **Rationale**: Prevents regressions and provides single-command verification for reviewers.
- **Verification Method**: `pytest tests/e2e/test_mock_pipeline.py`.
- **Acceptance Criteria**:
  - Test executes and passes in < 5 seconds with zero external network requests.
- **Dependencies**: All MVP functional requirements.
- **Release**: MVP
