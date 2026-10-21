# AgentOps

> Self-hosted AI Agent Operations Platform for verifiable, observable, and bounded research execution.

[![Status](https://img.shields.io/badge/Status-In%20Development%20(Phase%209)-orange)](#project-status)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

## Project Status

**Current Phase**: **Phase 22: Local Docker Compose Environment Finalized** (Complete)

AgentOps is an engineering portfolio project demonstrating production-grade AI systems engineering, deterministic orchestration, security boundaries, and observable operations.

- **Current Implementation State**: Fully functioning, end-to-end local Docker Compose environment unifying Next.js frontend, FastAPI backend API, Celery worker, PostgreSQL 16, Redis 7, and n8n Community. Includes LangGraph agent orchestration with deterministic mock mode, guarded tool sandboxing, traceable evidence collection, human-in-the-loop approvals, n8n notifications, OpenTelemetry observability, comprehensive test suites, and strict performance and capacity controls.

---

## Project Mission

AgentOps accepts a research or analysis request, validates the request against strict bounds, generates a validated execution plan, invokes approved tools, collects durable evidence, manages failures with bounded retries, requests human approval when necessary, and produces a traceable final report.

### Primary Demonstration: Industry Competitor Analysis
The flagship demonstration workflow analyzes competitors in a designated industry and geography using public, permitted sources. It compares products, market positioning, published pricing models, target customer segments, and recent public announcements, citing material factual claims and clearly distinguishing evidence from inference.

---

## Planned Architecture & Tech Stack

- **Backend API**: Python 3.10+, FastAPI (Pydantic v2 schemas, OpenAPI specs)
- **Agent Orchestrator**: LangGraph (deterministic state machine, state checkpointing)
- **Task Queue & Broker**: Celery + Redis (asynchronous execution, bounded timeouts)
- **Primary Database**: PostgreSQL (durable runs, event log, immutable evidence records)
- **Tool Sandbox**: Strict allowlisting with SSRF defense (no arbitrary shell or SQL)
- **Provider Adapters**: Pluggable architecture featuring a **Deterministic Mock Mode** (100% offline, zero paid API keys required), with optional adapters for OpenAI, Ollama, and Tavily.
- **Automation Integration**: Self-hosted n8n Community Edition for webhooks, triggers, and external notifications (core application rules remain in Python).
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS (run inspector, evidence drawer, HITL approval interface)
- **Containers**: Docker Compose (local-first, loopback-restricted dev ports)
- **Observability**: Structured JSON logging and OpenTelemetry tracing

---

## Product Constraints & Non-Goals

### Constraints
- **Local-first and Docker-based**: Operates reliably on a single workstation or development server.
- **Deterministic Mock Mode**: Can be fully evaluated, tested, and demonstrated without paid API keys.
- **Python-Owned Logic**: Core orchestration, validation, and business rules remain strictly in Python.
- **Zero Trust Boundaries**: Web pages, external API payloads, and LLM completions are treated as untrusted input.

### Explicit Non-Goals
- **No Multi-Tenant SaaS**: Does not include tenant isolation, Stripe billing, or SaaS user management.
- **No Unrestricted Swarms**: Does not implement dynamic, unconstrained multi-agent swarms.
- **No Arbitrary Code Execution**: The LLM is never permitted to execute arbitrary shell, SQL, or Python code.
- **No Uncontrolled Scraping**: Does not bypass CAPTCHAs, ignore robots.txt, or run aggressive crawler clusters.

---

## Project Documentation

Detailed system documentation is located in the [`docs/`](file:///Users/macbook/Downloads/Github_repo/agentops/docs/) directory:

- [00-product-vision.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/00-product-vision.md): Problem statement, mission, and demonstration scope.
- [01-scope-and-mvp.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/01-scope-and-mvp.md): In-scope MVP features, operating constraints, and explicit non-goals.
- [02-personas-and-user-stories.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/02-personas-and-user-stories.md): Detailed user personas and epic user stories with acceptance criteria.
- [03-success-metrics.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/03-success-metrics.md): Target metric categories and evaluation framework (distinguishing targets from measured results).
- [04-glossary.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/04-glossary.md): Terminology and architectural definitions.
- [05-product-requirements.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/05-product-requirements.md): Master PRD connecting vision, capabilities, and release phasing.
- [06-functional-requirements.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/06-functional-requirements.md): Testable functional requirements catalog (FR-01 to FR-14).
- [07-non-functional-requirements.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/07-non-functional-requirements.md): Verifiable quality attributes, latency budgets, and security bounds.
- [08-use-cases.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/08-use-cases.md): Primary competitor intelligence workflow, edge cases, and failure recovery.
- [09-acceptance-criteria.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/09-acceptance-criteria.md): Verification matrix and explicit MVP release gates.
- [10-mvp-backlog.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/10-mvp-backlog.md): MoSCoW-prioritized engineering backlog and deliberately deferred features.
- [11-system-architecture.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/11-system-architecture.md): Service architecture, container topology, state ownership, and failure recovery.
- [12-data-model.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/12-data-model.md): PostgreSQL relational schemas, ER diagram, Alembic migration strategy, and connection pools.
- [13-api-design.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/13-api-design.md): REST API v1 specification, request/response models, and webhook signatures.
- [14-security-threat-model.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/14-security-threat-model.md): Trust boundaries, STRIDE/OWASP threat mitigations, and SSRF defenses.
- [15-observability-design.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/15-observability-design.md): Structured JSON logging, OpenTelemetry distributed tracing, and audit events.
- [16-deployment-model.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/16-deployment-model.md): Docker Compose specification, container hardening, and GitHub Actions CI.
- [17-dependency-policy.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/17-dependency-policy.md): Dependency management policy, pinning rules, lockfiles, and license compliance.
- [18-runtime-compatibility.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/18-runtime-compatibility.md): Runtime compatibility matrix, Apple Silicon nuances, and execution topology.
- [19-development-workflow.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/19-development-workflow.md): Development workflow guide, code-quality standards, and troubleshooting.
- [local-infrastructure.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/runbooks/local-infrastructure.md): Operational guide for Docker Compose services, healthchecks, loopback security, and multi-database PostgreSQL.
- [backup-and-restore.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/runbooks/backup-and-restore.md): Procedures for database dumps, Redis persistence, volume backups, and safe non-destructive resets.
- [database-migrations.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/runbooks/database-migrations.md): Schema management guide, Alembic versioning, offline SQL generation, and rollback playbooks.
- [repository-scaffold.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/audits/repository-scaffold.md): Repository structure audit and conformance matrix.
- **Architecture Decision Records (ADRs)**:
  - [ADR-001: Core Technology Stack Selection](file:///Users/macbook/Downloads/Github_repo/agentops/docs/adr/ADR-001-technology-stack.md)
  - [ADR-002: Agent Orchestration Engine Selection (LangGraph)](file:///Users/macbook/Downloads/Github_repo/agentops/docs/adr/ADR-002-agent-orchestration.md)
  - [ADR-003: Asynchronous Background Execution (Celery + Redis)](file:///Users/macbook/Downloads/Github_repo/agentops/docs/adr/ADR-003-background-execution.md)
  - [ADR-004: Model & Provider Abstraction with Deterministic Mock Mode](file:///Users/macbook/Downloads/Github_repo/agentops/docs/adr/ADR-004-provider-abstraction.md)
  - [ADR-005: Local-First Deployment Strategy via Docker Compose](file:///Users/macbook/Downloads/Github_repo/agentops/docs/adr/ADR-005-local-first-deployment.md)
- [architecture.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/architecture.md): Technical topology and system design.
- [security.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/security.md): Security model, trust boundaries, and threat mitigation.
- [spec.md](file:///Users/macbook/Downloads/Github_repo/agentops/docs/spec.md): System functional specifications and interfaces.

---

## Baseline Verification (Local Setup)

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-username/agentops.git
cd agentops

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install baseline dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### 2. Run Verification Checks

```bash
# Verify baseline unit and security tests
pytest services/backend/tests
# Or use the Makefile
make test

# Verify formatting, linting, and type checking
make validate
```

### 3. Start Complete Local Docker Compose Environment

```bash
# Validate Docker Compose configuration and service dependency graph
docker compose -p agentops config

# Build and start all 6 cooperating services (Next.js, FastAPI, Celery, PostgreSQL, Redis, n8n)
docker compose -p agentops up -d --build

# Inspect service health and readiness
docker compose -p agentops ps

# Web Dashboard: http://127.0.0.1:3000
# Backend OpenAPI / Swagger: http://127.0.0.1:8000/docs
# n8n Automation Console: http://127.0.0.1:5678
```

### 4. Non-Destructive Shutdown and Reset

```bash
# Stop containers while preserving persistent database and n8n volumes
docker compose -p agentops stop

# Or teardown containers while keeping named volumes intact
docker compose -p agentops down

# (Optional) Full volume wipe and clean recreation
docker compose -p agentops down -v
```

---

## Repository Structure

```
agentops/
├── apps/
│   └── web/                 # Next.js frontend application (App Router, UI, hooks)
├── services/
│   └── backend/             # FastAPI API gateway, Celery workers & LangGraph
│       ├── app/
│       │   ├── api/v1/      # REST API route handlers
│       │   ├── core/        # Config, logging, SSRF security
│       │   ├── models/      # SQLAlchemy ORM models
│       │   ├── schemas/     # Pydantic v2 domain schemas
│       │   ├── repositories/# Data access layers
│       │   ├── services/    # Business domain services
│       │   ├── agents/      # LangGraph state machine & nodes
│       │   ├── tools/       # Guarded tool sandbox (web_search, fetch_document)
│       │   ├── providers/   # Provider adapters (Mock, OpenAI, Ollama, Tavily)
│       │   ├── workers/     # Celery tasks & queues
│       │   └── observability/# OpenTelemetry tracing & audit logs
│       ├── migrations/      # Alembic migration scripts
│       └── tests/           # Unit, integration, and contract tests
├── workflows/
│   └── n8n/                 # Self-hosted n8n templates (triggers, notifications)
├── evals/                   # Evaluation datasets, test cases, and baselines
├── infra/
│   ├── docker/              # Multi-stage Dockerfiles
│   ├── postgres/            # Database init & extensions
│   └── monitoring/          # OTel & Prometheus configs
├── scripts/                 # Development and operational utilities
├── docs/                    # Architecture, specifications, ADRs, and audits
├── compose.yaml             # Docker Compose deployment manifest
├── Makefile                 # Developer task runner
├── pyproject.toml           # Python package specifications & tool configs
└── README.md
```

---

## License

Apache-2.0
