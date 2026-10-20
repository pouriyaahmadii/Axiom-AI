# ADR-001: Core Technology Stack Selection

## Status
Accepted

## Context
AgentOps requires a robust, observable, maintainable, and verifiable technology stack capable of supporting:
1. High-performance asynchronous API endpoints for run submission and event streaming.
2. Type-safe relational data persistence for state, events, evidence, and audit logs.
3. Durable background execution of agent workflows off the HTTP request-response thread.
4. A modern, reactive, and accessible operator dashboard.
5. Integration with workflow automation for edge notifications.

## Decision
We select the following core technology stack:
- **Backend API**: Python 3.10+ with **FastAPI** and **Pydantic v2**.
- **Primary Database**: **PostgreSQL 16** with **SQLAlchemy 2.0** (`asyncpg` for API, `psycopg2` for Celery/migrations) and **Alembic**.
- **Task Queue & Broker**: **Celery 5.4+** backed by **Redis 7.2**.
- **Agent Orchestrator**: **LangGraph** (Python).
- **Edge Automation**: **n8n Community Edition**.
- **Frontend**: **Next.js (App Router)** with **React 18/19**, **TypeScript**, and **Tailwind CSS**.
- **Containerization**: **Docker Compose**.

## Alternatives Considered
1. **Node.js / NestJS for Backend**:
   - *Pros*: Single language across frontend and backend.
   - *Cons*: The AI and agent ecosystem (LangGraph, token modeling, scientific data structures) is predominantly Python-native. Developing agent graphs in TypeScript introduces significant ecosystem friction.
2. **Go (Golang) for Backend**:
   - *Pros*: Extreme concurrency, low memory footprint, single binary.
   - *Cons*: Immature AI agent orchestration ecosystem; lack of official LangGraph framework support.
3. **MongoDB or DynamoDB for Persistence**:
   - *Pros*: Flexible document schemas for dynamic model outputs.
   - *Cons*: Weak transactional guarantees across multi-entity runs (e.g., Run -> Step -> Evidence -> Approval); lacks ACID compliance for durable checkpoints.

## Consequences
- **Positive**:
  - Python gives direct access to first-class AI orchestration libraries and deterministic typing via Pydantic v2.
  - PostgreSQL guarantees transactional consistency, foreign key integrity, and relational audit trails.
  - Celery provides mature task timeouts, retries, worker concurrency control, and dead-letter handling.
  - FastAPI provides native async execution and automatic OpenAPI documentation.
- **Negative / Trade-offs**:
  - Dual-language stack (Python backend, TypeScript frontend) requires maintaining two separate runtime environments.
  - Celery requires a dedicated message broker (Redis), adding operational components compared to an in-process thread pool.

## Rejected Options
- **Pure n8n for Orchestration**: Rejected because business logic, agent validation, safety limits, and state checkpoints must be auditable in code rather than hidden in proprietary canvas JSONs.
- **SQLite for Production / Multi-Process Storage**: Rejected because SQLite has concurrency write bottlenecks when accessed simultaneously by async API processes and multiple background workers.

## Conditions for Revisiting
- If Python's GIL or memory overhead severely restricts high-concurrency multi-worker scaling, or if a unified language stack becomes a paramount business requirement.
