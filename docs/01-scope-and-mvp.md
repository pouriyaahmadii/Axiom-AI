# Scope and MVP Definition: AgentOps

## 1. MVP Objective

The AgentOps Minimum Viable Product (MVP) establishes a complete, verified, and self-hosted execution environment for structured AI research tasks. It proves that an AI coordinator can reliably plan, execute allowlisted tools, pause for operator approval, collect grounded evidence, and generate verifiable reports within strict operational and security boundaries.

---

## 2. In-Scope Capabilities (MVP)

### 2.1 Request Ingestion & Validation
- **Structured Submission**: REST API endpoint accepting research objectives, industry/domain parameters, geographical scope, and optional constraints.
- **Strict Input Validation**: Pydantic v2 validation enforcing schema integrity, length constraints, and parameter bounds.
- **Run Tracking**: Generation of unique run identifiers (`run_id`) and initial run state initialization in PostgreSQL.

### 2.2 Orchestration & Planning (Python & LangGraph)
- **Bounded Plan Generation**: Deconstruction of research requests into a discrete Directed Acyclic Graph (DAG) of steps (`PlanStep`).
- **Plan Validation**: Pre-execution verification ensuring step count does not exceed `MAX_PLAN_STEPS` (default: 10) and that all requested tools are allowlisted.
- **State Checkpointing**: Persistent serialization of execution graph state after each node transition to enable pause, resume, and fault recovery.

### 2.3 Safe Tool Execution Layer
- **Allowlisted Tools Only**:
  - `web_search`: Query search providers (Mock or Tavily/DuckDuckGo) with sanitized search queries.
  - `fetch_document`: Retrieve web content with mandatory Server-Side Request Forgery (SSRF) IP/domain filtering and size limits.
  - `extract_metrics`: Structured parsing of financial/operational data (pricing, dates, headcount).
- **Security Boundaries**: Absolute prohibition of shell execution, raw SQL execution, or dynamic Python `eval`.
- **Resource Constraints**: Enforcement of per-step timeouts (`STEP_TIMEOUT_SECONDS`), overall run timeouts (`MAX_EXECUTION_SECONDS`), and automated retry limits (`MAX_RETRIES_PER_STEP`).

### 2.4 Evidence & Citation Tracking
- **Immutable Evidence Store**: Preservation of raw retrieved snippets, source URLs, content hashes (SHA-256), and timestamps in an `EvidenceRecord` table.
- **Citation Grounding**: Automated mapping of extracted claims to recorded evidence identifiers.
- **Inference Separation**: Explicit categorization of report sections into "Factual Evidence" and "Synthesized Inference / Analysis".

### 2.5 Human-in-the-Loop (HITL) Approval
- **Consequential Action Gates**: Automated pauses when a plan step flags `requires_human_approval = True` (e.g., dispatching external notifications or publishing artifacts).
- **Approval Tokens**: Cryptographic token generation and PostgreSQL status tracking (`pending`, `approved`, `rejected`).
- **Resume Capability**: Seamless graph resumption upon operator verdict submission via API or UI.

### 2.6 Pluggable Adapter Architecture
- **Deterministic Mock Mode (Default)**: Offline execution using deterministic mock LLM completions and a pre-packaged competitor analysis research corpus. Requires zero paid API keys.
- **Optional Live Adapters**: Drop-in configuration for OpenAI-compatible APIs, local Ollama models, and Tavily search.

### 2.7 Automation & Asynchronous Processing
- **Background Tasks**: Celery workers executing LangGraph state machines off the main API thread.
- **Message Broker**: Redis handling job queues and real-time state broadcasts.
- **n8n Community Integration**: Standalone workflow triggering runs via incoming webhooks and dispatching completion notifications.

### 2.8 User Interface (Next.js & TypeScript)
- **Run Control Center**: Form for submitting research requests with configurable mock/live toggles.
- **Execution Inspector**: Live visualization of plan steps, current execution status, and event timeline.
- **HITL Modal**: Dedicated interactive prompt for reviewing and approving pending actions.
- **Evidence Drawer & Report Viewer**: Markdown report reader with clickable citation backlinks linking directly to source snippets.

---

## 3. Explicit Non-Goals (Out of Scope for MVP)

To ensure high architectural rigor and prevent speculative scope creep, the following capabilities are explicitly **Out of Scope**:

1. **Multi-Tenant SaaS Infrastructure**: No organization hierarchy, billing integration (e.g., Stripe), team permissions, or subscription management. AgentOps MVP is designed as a single-operator or team-shared self-hosted utility.
2. **Autonomous Multi-Agent Swarms**: No unrestricted inter-agent debates, dynamic role synthesis, or emergent swarming. The architecture adheres strictly to a single-coordinator pattern with explicit task delegation.
3. **Arbitrary Code or Shell Execution**: No dynamic code sandboxes (e.g., Docker-in-Docker code runners, e2b) executing LLM-generated Python or shell scripts.
4. **Aggressive Web Crawling**: No headless browser clusters (e.g., Selenium/Puppeteer clusters) designed to bypass anti-bot systems, solve CAPTCHAs, or scrape authenticated web applications.
5. **Proprietary Vector Database Clusters**: No dedicated vector databases (Pinecone, Qdrant cluster). Simple structured semantic matching or relational evidence lookups in PostgreSQL suffice for the MVP.
6. **Production Cloud Claims**: No claim of high-scale cloud production readiness from a local Docker Compose deployment alone.

---

## 4. Product Assumptions & Operating Constraints

- **Host Environment**: Docker and Docker Compose installed on standard x86_64 or Apple Silicon architectures.
- **Network Defaults**: All services bind to loopback (`127.0.0.1`) by default during local development to prevent unintended exposure.
- **Deterministic Mock Corpus**: The competitor research demonstration includes canned, high-fidelity data representing typical industry profiles to ensure repeatable testing.
