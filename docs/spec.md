# AgentOps: System & Functional Specification

## 1. Functional Requirements

### 1.1 Request Submission
- The system must accept a structured research or analysis request containing a objective description, constraints, and optional execution parameters.
- Validates input format and generates a unique `run_id`.

### 1.2 Execution Planning
- Deconstructs research requests into a discrete, bounded sequence of steps (`ExecutionPlan`).
- Each step specifies: `step_id`, `title`, `tool_name`, `parameters`, `requires_human_approval`, and `dependencies`.
- Validates that total plan steps do not exceed `MAX_PLAN_STEPS` (default: 10).

### 1.3 Safe Tool Execution
- Invokes allowlisted tools only (e.g., `web_search`, `fetch_document`, `calculate_metrics`).
- Enforces SSRF checks on any URL retrieval.
- Records exact tool inputs, outputs, timestamps, and status into immutable execution events.

### 1.4 Evidence & Citation Tracking
- Extracts factual claims and anchors them to verifiable source snippets (`EvidenceRecord`).
- Computes content hashes and verifies citation grounding before report inclusion.

### 1.5 Human Approval Gates
- When a step flags `requires_human_approval = True`, the LangGraph orchestrator pauses execution and records an `ApprovalRequest`.
- An authorized human operator can review the pending parameters and issue an `approved` or `rejected` verdict.
- Execution only resumes upon verified approval.

### 1.6 Traceable Final Report
- Synthesizes findings into a structured markdown report.
- Includes an explicit bibliography/citations list linking claims directly to recorded evidence IDs.
- Reports execution metadata: total time, steps executed, cost, model used.

## 2. Interface Contracts

- **FastAPI Endpoints**:
  - `GET /` & `GET /api/v1/health`: Service health and provider info.
  - `POST /api/v1/runs`: Submit research request.
  - `GET /api/v1/runs/{run_id}`: Poll run state, active step, and event timeline.
  - `POST /api/v1/runs/{run_id}/approvals/{approval_id}`: Submit HITL approval verdict.
  - `GET /api/v1/runs/{run_id}/report`: Retrieve synthesized report with citations.
