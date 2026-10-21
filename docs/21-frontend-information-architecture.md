# Frontend Information Architecture (`docs/21-frontend-information-architecture.md`)

## 1. Overview & Information Goals

The AgentOps frontend provides engineering operators and analysts with complete observational visibility, lifecycle control, and auditability over asynchronous agentic workflows.

### Primary Information Goals
1. **At-a-Glance Operational Health**: Instant assessment of active runs, queued tasks, and human-in-the-loop approval bottlenecks.
2. **Deterministic Step-by-Step Traceability**: Real-time inspection of the LangGraph execution plan, active step parameters, tool call payloads, and status transitions.
3. **Evidence Grounding Verification**: Direct inspection of primary sources, content hashes, extracted claims, and contradiction flags.
4. **Actionable Governance & Oversight**: Frictionless approval or rejection of gated actions with clear payload hashes, operator notes, and time-to-live warnings.
5. **Grounded Reporting**: Clean, distraction-free reading experience for synthesized research reports with interactive inline citation popovers.

---

## 2. Page & Route Hierarchy

```
/ (Root)
│
├── /dashboard                    -> Operational Dashboard (Active runs, approval alerts, recent history)
│
├── /runs
│   ├── /new                     -> New Analysis Submission (Objective, domain, geography, budget limits)
│   └── /[id]                    -> Run Details Hub (Unified multi-tab workspace for a single run)
│       ├── /overview            -> Run summary, budget tracking, error logs, metadata
│       ├── /timeline            -> Execution Plan DAG & sequential step status tracker
│       ├── /evidence            -> Captured sources, evidence passages, extracted facts
│       └── /report              -> Synthesized research report with citations
│
├── /approvals                   -> Global Approval Inbox (Pending, resolved, and expired HITL gates)
│
├── /evidence                    -> Global Evidence Explorer (Search sources, domains, and claims)
│
├── /audit                       -> System Audit History (Immutable event stream, actors, and payloads)
│
└── /settings                    -> System Settings & Limits (Provider modes, budget defaults, API endpoints)
```

---

## 3. Screen Specifications & Data Requirements

### 3.1 Dashboard (`/` & `/dashboard`)
- **Purpose**: High-level command center showing platform status and active agent workloads.
- **Key Sections**:
  - **Metric Stat Cards**: Active Runs, Pending Approvals, Total Completed (24h), Estimated Spend vs Budget.
  - **Action Required Banner**: Prominent callout when approvals are blocking execution.
  - **Active Workloads Table**: Live table showing running/planning tasks with elapsed time and current step.
  - **Recent Runs Feed**: Paginated list with objective summary, domain pill, status badge, and duration.
- **Data Source**: `GET /api/v1/runs?limit=10`, `GET /api/v1/health`, `GET /api/v1/info`.

---

### 3.2 New Analysis Submission (`/runs/new`)
- **Purpose**: Operator form to configure and trigger an asynchronous analytical research workflow.
- **Form Controls**:
  - `Objective` (Textarea, required, 10–2000 characters).
  - `Domain` (Select / text input, required, e.g. `ai-observability`, `devtools`).
  - `Geography` (Text input, optional, default: `Global`).
  - `Budget Limit USD` (Number input, step 0.10, default: `$1.00`, ceiling: `$5.00`).
  - `Execution Mode` (Radio: `Mock Mode (Deterministic)` vs `Live Provider (Requires API Keys)`).
  - `HITL Gates` (Checkboxes: Review Execution Plan, Review Tool Calls, Review Final Report).
- **Behavior**: Submits to `POST /api/v1/runs`, redirects to `/runs/[id]` upon receiving `202 Accepted`.

---

### 3.3 Run Details Hub (`/runs/[id]`)
- **Purpose**: Centralized multi-tab console for inspecting an individual research run.
- **Global Header**:
  - Run ID with copy button, Objective heading, Status badge, Started/Completed timestamps, Cancel Run button.
- **Tabs**:
  1. **Overview Tab**: Core metadata, provider selection, cost breakdown, error summaries, raw parameters.
  2. **Timeline Tab (`/runs/[id]/timeline`)**: Visual step-by-step sequential timeline of the plan DAG. Each step displays tool name, status, retry count, runtime duration, and parameter diff.
  3. **Evidence Tab (`/runs/[id]/evidence`)**: Table of all gathered web sources, content hashes, retrieval timestamps, and extracted factual claims.
  4. **Report Tab (`/runs/[id]/report`)**: Complete synthesized Markdown report with inline citations, executive summary, and export options.

---

### 3.4 Approval Inbox (`/approvals`)
- **Purpose**: Dedicated triage queue for pending human-in-the-loop authorization gates.
- **Key Elements**:
  - Filter tabs: `Pending (Needs Action)`, `Approved`, `Rejected`, `Expired`.
  - Approval Card / Row:
    - Target Run Objective & ID link.
    - Proposed Action type (`PLAN_REVIEW`, `STEP_EXECUTION`, `REPORT_REVIEW`).
    - Expiration countdown timer.
    - Proposed payload preview with SHA-256 hash.
    - Action Dialog: Operator input for feedback notes and Approve/Reject buttons.
- **Data Source**: `GET /api/v1/runs?status=AWAITING_APPROVAL`, `POST /api/v1/approvals/{id}/approve`, `POST /api/v1/approvals/{id}/reject`.

---

### 3.5 Global Evidence Explorer (`/evidence`)
- **Purpose**: Searchable index of all verified knowledge sources and extracted entity claims.
- **Filters**: By domain, source type (`PUBLIC_PAGE`, `API_DOCUMENTATION`, `SEARCH_RESULT`), validation status.
- **Details Drawer**: Slide-over panel showing full captured excerpt, normalized URL, and referencing run IDs.

---

### 3.6 System Audit History (`/audit`)
- **Purpose**: Security, observability, and compliance log for all platform transactions.
- **Key Columns**: Timestamp (UTC), Correlation ID, Event Type pill (`RUN_QUEUED`, `TOOL_CALLED`, `APPROVAL_RESOLVED`), Actor (`operator`, `agent`, `system`), Payload JSON preview.
- **Data Source**: `GET /api/v1/runs/{id}/events`.

---

### 3.7 Settings (`/settings`)
- **Purpose**: Operational bounds, provider toggle, and diagnostic verification.
- **Sections**:
  - **Runtime Limits**: View `max_plan_steps`, `max_execution_seconds`, and budget caps.
  - **Dependency Diagnostics**: Live health status of FastAPI, PostgreSQL, Redis, and n8n.
  - **Theme & Display**: Light / Dark mode toggle, reduced-motion toggle.

---

## 4. Shared Application Shell Layout

```
+-----------------------------------------------------------------------------------------+
|                                    Top Header Bar                                       |
| [Logo] AgentOps Console    [Search / Run ID...]       [Health: OK] [Theme Toggle] [API Docs] |
+------------------+----------------------------------------------------------------------+
|     Sidebar      |                                                                      |
|  - Dashboard     |  [Breadcrumbs: Runs > run-9f8a... > Timeline]                         |
|  - New Analysis  |                                                                      |
|  - Approvals (2) |  [Main Canvas Content: Dense, Structured, Accessible]                |
|  - Evidence      |                                                                      |
|  - Audit Log     |                                                                      |
|  - Settings      |                                                                      |
|                  |                                                                      |
|  [System Status] |                                                                      |
+------------------+----------------------------------------------------------------------+
```

- **Collapsible Sidebar**: On desktop (240px expanded, 64px icon-only collapsed).
- **Responsive Drawer**: On mobile (< 768px), accessible via standard header hamburger button with overlay backdrop.
- **Keyboard Shortcuts**: `/` to focus global search, `g d` for Dashboard, `g a` for Approvals, `g n` for New Analysis.
