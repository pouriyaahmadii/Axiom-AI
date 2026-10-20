# ADR-003: Asynchronous Background Execution (Celery + Redis)

## Status
Accepted

## Context
AI research workflows involve multi-step tool calls, model inferences, and human approval pauses that take from tens of seconds up to several minutes. Executing these operations within a synchronous HTTP request thread in FastAPI would:
1. Block web server worker threads.
2. Cause client HTTP connection timeouts (gateways typically timeout at 30–60s).
3. Risk total job loss if the web server restarts or is reloaded.
Therefore, run execution must be decoupled from the HTTP lifecycle.

## Decision
We select **Celery** with **Redis** as the asynchronous task execution and message brokering system:
- The FastAPI gateway accepts a research request, inserts the initial `Run` record with status `QUEUED` in PostgreSQL, publishes a task message to Celery via Redis, and returns HTTP 201 immediately with the `run_id`.
- Dedicated Celery worker processes pull task messages, initialize the LangGraph state machine, and execute steps asynchronously.
- Task status, progress events, and state checkpoints are committed transactionally to PostgreSQL.

## Alternatives Considered
1. **FastAPI `BackgroundTasks`**:
   - *Pros*: Built-in, zero external infrastructure required.
   - *Cons*: Executes in the same process memory as the web server; tasks are killed if the web server restarts; lacks task concurrency controls, task revocation, and distributed worker scaling.
2. **ARQ (Async Redis Queue)**:
   - *Pros*: Native `asyncio` worker written for modern Python.
   - *Cons*: Smaller ecosystem, fewer operational management tools, and less battle-tested task revocation compared to Celery.
3. **Temporal.io**:
   - *Pros*: Best-in-class durable execution and workflow replay.
   - *Cons*: High operational complexity requiring a dedicated Temporal cluster, database, and Go-based server components; excessive for local-first MVP.

## Consequences
- **Positive**:
  - Web API remains lightweight, responsive, and resilient to long-running task stalls.
  - Celery provides mature worker process supervision, concurrency controls, task timeouts, and clean task cancellation.
  - Decouples API scaling from worker resource scaling (e.g., CPU/memory allocations).
- **Negative / Trade-offs**:
  - Requires running and maintaining a Redis container.
  - Celery requires separate worker processes and careful handling of database connection pooling across forks.

## Rejected Options
- **Synchronous In-Request Execution**: Rejected because HTTP timeouts would break any multi-step research workflow exceeding 30 seconds.
- **Thread Pool Executor in FastAPI**: Rejected due to lack of durability and process isolation.

## Conditions for Revisiting
- If native Python `asyncio` worker frameworks (such as ARQ) achieve feature parity with Celery's revocation/monitoring ecosystem and reduce deployment footprint.
