# Product Requirements Document (PRD): AgentOps

## 1. Document Overview

This Product Requirements Document (PRD) defines the foundational product architecture, requirements structure, operational boundaries, and release planning for **AgentOps**. AgentOps is a self-hosted, observable, and secure AI Agent Operations Platform engineered for verifiable analytical research, deterministic orchestration, and human-in-the-loop governance.

---

## 2. Product Objectives & Strategy

### 2.1 Core Mission
To provide technical evaluators, research analysts, and systems engineers with a reliable, local-first platform for orchestrating AI research workflows. Unlike opaque "black-box" agents, AgentOps guarantees that every action is bounded, every tool call is authorized, every factual claim is grounded in verifiable evidence, and every consequential operation is subject to human oversight.

### 2.2 Strategic Value Drivers
1. **Verifiable Engineering Portfolio**: Showcases production-quality distributed systems design in Python (FastAPI, LangGraph, Celery, PostgreSQL), modern TypeScript/Next.js frontend design, and security engineering.
2. **Deterministic Reliability**: Eliminates dependence on brittle external API keys through a robust, seed-reproducible local Mock Mode.
3. **Defense in Depth**: Prevents common agent vulnerabilities—such as Server-Side Request Forgery (SSRF), prompt injection escapement, and infinite execution loops—by enforcing deterministic schema boundaries.
4. **Separation of Concerns**: Core orchestration remains strictly within auditable Python code; external workflow engines (n8n) are restricted to edge notifications and ingestion triggers.

---

## 3. Product Architecture & Capability Matrix

AgentOps is decomposed into five primary functional subsystems:

```
+-----------------------------------------------------------------------------------+
|                                Next.js Frontend                                   |
|   (Run Submission, Live Plan Inspector, Event Logs, HITL Modal, Report Viewer)   |
+-----------------------------------------+-----------------------------------------+
                                          | REST / SSE
                                          v
+-----------------------------------------------------------------------------------+
|                                FastAPI Backend                                    |
|   (Schema Validation, Run Management, Approval Tokens, OpenTelemetry Tracing)     |
+-------------------+-------------------------------------------+-------------------+
                    |                                           |
                    v                                           v
+---------------------------------------+   +---------------------------------------+
|          PostgreSQL Database          |   |          Redis Task Broker            |
| (Durable State, Events, Evidence,     |   | (Job Queues, Celery Worker Messages,  |
|  Approval Records, Final Reports)     |   |  Real-time State Synchronization)     |
+---------------------------------------+   +-------------------+-------------------+
                                                                |
                                                                v
+-----------------------------------------------------------------------------------+
|                             Celery Execution Workers                              |
|   +---------------------------------------------------------------------------+   |
|   |                        LangGraph State Coordinator                        |   |
|   |   (Plan DAG -> Step Loop -> HITL Pause/Resume -> Evidence -> Synthesize)  |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   |                   Guarded Tool Sandbox & Provider Adapters                |   |
|   |   (SSRF Guard, Allowlisted Tools, Mock / Live LLM & Search Adapters)      |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Release Strategy & Phasing

AgentOps development follows a strict MoSCoW prioritization model across two release milestones:

### 4.1 Release Milestone 1: Minimum Viable Product (MVP)
The MVP proves the end-to-end viability of the platform using a single-coordinator pattern, local Docker Compose orchestration, a complete deterministic mock demonstration, and a competitor research use case.
- **Target Audience**: Technical evaluators, hiring managers, and self-hosting analysts.
- **Core Features**: Request validation, bounded DAG planning, SSRF-safe tool registry, PostgreSQL state checkpoints, HITL approval gate, Celery worker queue, Next.js operational UI, and automated test coverage.

### 4.2 Release Milestone 2: Post-MVP & Extended Capabilities
Features that enhance scaling, collaborative enterprise workflows, or multi-modal analysis, deliberately deferred to prevent speculative scope creep during initial evaluation:
- Native multi-tenant organization workspaces with Role-Based Access Control (RBAC).
- Dynamic vector indexing with hybrid dense/sparse embeddings.
- Multi-user real-time collaborative annotation of research reports.
- Self-optimizing plan reflection and multi-agent debate synthesis.

---

## 5. Cross-Document Navigation

This PRD serves as the parent document for the complete requirements specification:
- [06-functional-requirements.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/06-functional-requirements.md): Exhaustive functional requirements catalog (FR-01 to FR-14).
- [07-non-functional-requirements.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/07-non-functional-requirements.md): Quality attributes, performance, security, and developer experience (NFR-01 to NFR-11).
- [08-use-cases.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/08-use-cases.md): Step-by-step operational workflows, primary competitor analysis, and failure recovery.
- [09-acceptance-criteria.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/09-acceptance-criteria.md): Verification criteria matrix, quality gate definitions, and sign-off criteria.
- [10-mvp-backlog.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/10-mvp-backlog.md): MoSCoW-prioritized epics, user stories, engineering tasks, and deferred backlog.
