# AgentOps Backend Service (`services/backend`)

FastAPI backend API and Celery background workers for research workflow orchestration.

## Package Structure
- `app/api/v1/routes/`: Versioned REST API route handlers.
- `app/core/`: Application settings, security primitives (SSRF guard), and structured logging.
- `app/db/`: Database session management and base declarative configurations.
- `app/models/`: SQLAlchemy 2.0 ORM database models.
- `app/schemas/`: Pydantic v2 domain schemas, input validators, and response envelopes.
- `app/repositories/`: Data access layers for runs, plans, events, evidence, and approvals.
- `app/services/`: Application domain services coordinating API and execution workflows.
- `app/agents/`: LangGraph coordinator, state machine definitions, and node logic.
- `app/tools/`: Allowlisted tool implementations (`web_search`, `fetch_document`, `extract_metrics`).
- `app/providers/`: Provider adapter interfaces and implementations (`Mock`, `OpenAI`, `Ollama`, `Tavily`).
- `app/workers/`: Celery application instance, task definitions, and broker configurations.
- `app/observability/`: OpenTelemetry distributed tracing and metrics instrumentation.
- `migrations/`: Alembic database migration scripts.
- `tests/`:
  - `unit/`: Isolated unit tests for schemas, security, and adapters.
  - `integration/`: Multi-component tests with database and broker fixtures.
  - `contract/`: API schema validation and provider contract tests.

## Running Tests

```bash
pytest services/backend/tests
```
