# Personas and User Stories: AgentOps

## 1. User Personas

### Persona A: The Technical Evaluator (Alex)
- **Role**: Staff Software Engineer / Hiring Manager reviewing the AgentOps repository for a technical portfolio assessment.
- **Goals**: Verify software craftsmanship, architectural clarity, security boundaries, testing rigor, and proper separation of concerns.
- **Pain Points**: Frustrated by repositories that only work with paid API keys, claim features that do not exist, hide application logic in proprietary workflow tools, or use unrestricted LLM execution.
- **Key Need**: Clone the repository, run automated tests (`pytest`, `ruff`), launch via Docker Compose in deterministic mock mode without API keys, and inspect an auditable codebase.

### Persona B: The Competitive Research Analyst (Elena)
- **Role**: Business Analyst / Market Researcher conducting competitive intelligence.
- **Goals**: Generate a structured, objective competitor teardown comparing products, pricing, positioning, and announcements within a target market.
- **Pain Points**: Manual search takes hours; standard LLM outputs hallucinate pricing and feature claims without citations.
- **Key Need**: Submit a research topic, review the execution plan, inspect source citations for factual grounding, approve any external publishing, and read a report clearly distinguishing facts from model inferences.

### Persona C: The Platform / DevOps Engineer (Marcus)
- **Role**: Systems Engineer deploying and maintaining self-hosted operations tooling.
- **Goals**: Ensure predictable resource usage, easy observability via structured logs/OpenTelemetry, and zero security risks to internal networks.
- **Pain Points**: Autonomous agents scanning internal networks (SSRF), running out of memory, or leaking API keys in repositories.
- **Key Need**: Run the entire stack securely on loopback interfaces via Docker Compose, monitor execution state in PostgreSQL, and configure strict timeout and budget bounds.

---

## 2. User Stories by Epic

### Epic 1: Request Ingestion & Plan Validation

#### US-1.1: Submit Research Objective
> **As an** Analyst,  
> **I want to** submit a competitive research request specifying industry, geography, and target competitor parameters,  
> **So that** the platform can begin orchestrated analysis without manual data gathering.
- **Acceptance Criteria**:
  - **Given** a valid JSON request payload conforming to `RunRequest`,
  - **When** submitted to `POST /api/v1/runs`,
  - **Then** the API returns HTTP 201 with a unique `run_id`, initializes run state in PostgreSQL, and enqueues the execution job in Celery.

#### US-1.2: Deterministic Plan Generation & Validation
> **As an** Operator,  
> **I want** the system to construct and validate a discrete step-by-step execution plan before invoking tools,  
> **So that** the agent cannot execute arbitrary, infinite, or unallowlisted actions.
- **Acceptance Criteria**:
  - **Given** an enqueued research run,
  - **When** the LangGraph planner node processes the objective,
  - **Then** it generates an `ExecutionPlan` containing no more than `MAX_PLAN_STEPS` steps, where every step specifies an allowlisted tool, and rejects any plan with unknown tools or circular dependencies.

---

### Epic 2: Guarded Tool Execution & Evidence Collection

#### US-2.1: SSRF-Protected Web Retrieval
> **As a** DevOps Engineer,  
> **I want** all URL fetching tools to validate target IP addresses and hostnames,  
> **So that** the agent cannot scan internal network subnets or cloud metadata services.
- **Acceptance Criteria**:
  - **Given** an execution step requesting a URL,
  - **When** the tool attempts retrieval,
  - **Then** the request is blocked and logged if the host resolves to loopback (`127.0.0.1`), private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), or cloud metadata (`169.254.169.254`).

#### US-2.2: Structured Evidence Grounding
> **As an** Analyst,  
> **I want** all factual claims anchored to immutable evidence records with content hashes,  
> **So that** I can verify source authenticity and prevent model hallucinations.
- **Acceptance Criteria**:
  - **Given** successful tool execution returning raw text snippets,
  - **When** the coordinator processes the tool output,
  - **Then** it creates an `EvidenceRecord` storing source URL, SHA-256 content hash, retrieval timestamp, and exact snippet in PostgreSQL.

---

### Epic 3: Human-in-the-Loop (HITL) Oversight

#### US-3.1: Execution Pause on Consequential Action
> **As an** Operator,  
> **I want** the agent to halt execution when a step involves consequential external effects,  
> **So that** I can review proposed actions before they are executed.
- **Acceptance Criteria**:
  - **Given** an execution plan step with `requires_human_approval = True`,
  - **When** the state graph transitions to this step,
  - **Then** execution is paused, run status is updated to `AWAITING_APPROVAL`, a unique approval token is generated, and a webhook notification is dispatched.

#### US-3.2: Operator Verdict Submission
> **As an** Operator,  
> **I want to** approve or reject a pending approval request via UI or API,  
> **So that** execution can safely proceed or abort based on human discretion.
- **Acceptance Criteria**:
  - **Given** a run in `AWAITING_APPROVAL` status,
  - **When** the operator posts `{"verdict": "approved"}` to the approval endpoint,
  - **Then** the state graph resumes execution from the exact checkpointed state.

---

### Epic 4: Traceable Final Report & Inspection

#### US-4.1: Evidence vs. Inference Separation
> **As an** Analyst,  
> **I want** the final research report to visually and structurally separate empirical evidence from model deductions,  
> **So that** I can critically evaluate analytical conclusions.
- **Acceptance Criteria**:
  - **Given** completed evidence collection and synthesis,
  - **When** the final report is generated,
  - **Then** it contains dedicated sections for "Empirical Evidence & Findings" with clickable citation markers, and a distinct section for "Market Inference & Strategic Commentary".

#### US-4.2: Full Execution Audit Trail
> **As a** Technical Evaluator,  
> **I want to** inspect the step-by-step event log and timeline of any run,  
> **So that** I can assess orchestrator behavior, retry counts, latency, and token/cost budgets.
- **Acceptance Criteria**:
  - **Given** any historical `run_id`,
  - **When** queried via `GET /api/v1/runs/{run_id}`,
  - **Then** the response provides a complete chronological list of execution events, step durations, and budget consumption.

---

### Epic 5: Self-Hosting & Deterministic Mock Evaluation

#### US-5.1: Zero-Key Local Demonstration
> **As a** Technical Evaluator,  
> **I want to** run a complete end-to-end competitor research cycle without providing paid API keys,  
> **So that** I can verify the platform's orchestration and UI deterministically.
- **Acceptance Criteria**:
  - **Given** `.env` configured with `LLM_PROVIDER=mock` and `SEARCH_PROVIDER=mock`,
  - **When** a research run is triggered,
  - **Then** the entire workflow (plan, tool call, HITL pause, report) completes successfully using reproducible mock data with 100% test pass rate.
