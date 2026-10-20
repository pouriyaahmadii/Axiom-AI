# Database Migrations Runbook (`docs/runbooks/database-migrations.md`)

This runbook documents the schema management lifecycle, migration commands, safety guidelines, and rollback procedures for AgentOps using Alembic and SQLAlchemy 2.0.

---

## 1. Architecture & Migration Strategy

AgentOps uses **Alembic** to manage all relational database schema evolutions. The application enforces a strict versioned migration strategy:
- **No Automatic DDL on Startup**: Neither FastAPI nor Celery workers call `Base.metadata.create_all()` on process boot. Schema creation is strictly driven by versioned migrations.
- **Single Source of Truth**: All domain entities inherit from `app.db.base.Base` and are cataloged in `app.models`.
- **Dialect Portability**: Columns using `JSONBType` emit PostgreSQL `JSONB` on PostgreSQL clusters and fall back to native `JSON` on SQLite for local testing. UUIDs utilize `sa.Uuid()`.

### Pinned Database Entities (10 Core Models)

| Entity | Table Name | Primary Key | Key Constraints & Idempotency |
| :--- | :--- | :--- | :--- |
| **Run** | `runs` | UUIDv4 | Unique `idempotency_key`, indexed `status`, `correlation_id`. |
| **RunStep** | `run_steps` | UUIDv4 | Unique `(run_id, step_index)`, unique `(run_id, step_identifier)`. |
| **Source** | `sources` | UUIDv4 | Unique `(run_id, url)`, indexed `content_hash`, `domain`. |
| **ToolInvocation** | `tool_invocations` | UUIDv4 | Indexed `(run_id, tool_name)`, indexed `(run_id, idempotency_key)`. |
| **EvidenceItem** | `evidence_items` | UUIDv4 | Unique `(run_id, content_hash)` prevents duplicate evidence per run. |
| **Approval** | `approvals` | UUIDv4 | Unique `approval_token`, unique `(run_id, step_id)`. |
| **Report** | `reports` | UUIDv4 | Unique `run_id` (1-to-1 relationship with Run). |
| **LLMCall** | `llm_calls` | UUIDv4 | Indexed `(run_id, provider)`. Never stores API keys. |
| **AuditEvent** | `audit_events` | UUIDv4 | Immutable append-only audit log; ORM update/delete blocked. |
| **OutboxEvent** | `outbox_events` | UUIDv4 | Transactional outbox for reliable async event delivery. |

---

## 2. Directory Structure & Key Files

```
services/backend/
├── alembic.ini                    # Alembic global configuration
├── migrations/
│   ├── env.py                     # Runtime migration execution environment
│   ├── script.py.mako             # Revision template
│   └── versions/                  # Versioned migration revision files
│       └── 0001_initial_domain_model.py
└── app/
    ├── db/
    │   ├── base.py                # Base DeclarativeBase, JSONBType, Mixins
    │   └── session.py             # Async & sync engine session factories
    └── models/                    # Domain model definitions
```

---

## 3. Standard Operational Procedures

All migration commands are executed from `services/backend/` using the project's Python virtual environment.

### 3.1 Initializing a Fresh Database
To apply all pending migrations up to the latest revision (`head`):
```bash
cd services/backend
../../.venv/bin/alembic upgrade head
```

### 3.2 Inspecting Migration Status
```bash
# Check current database revision
cd services/backend
../../.venv/bin/alembic current

# View complete migration history
cd services/backend
../../.venv/bin/alembic history --verbose
```

### 3.3 Generating Migration SQL Offline (Dry-Run / Audit)
Before applying migrations to a shared staging or production cluster, generate the raw static SQL without executing it:
```bash
cd services/backend
../../.venv/bin/alembic upgrade head --sql
```

### 3.4 Rolling Back / Downgrading Migrations
To step backward by one revision:
```bash
cd services/backend
../../.venv/bin/alembic downgrade -1
```

To roll back all revisions back to an empty database:
```bash
cd services/backend
../../.venv/bin/alembic downgrade base
```

### 3.5 Creating a New Revision
When domain models in `app/models/` are modified, generate a new versioned migration:
```bash
cd services/backend
../../.venv/bin/alembic revision --autogenerate -m "add_search_reranking_fields"
```

> [!IMPORTANT]
> Always manually inspect auto-generated migration scripts in `migrations/versions/` to verify constraint naming, foreign keys, and reversible `downgrade()` logic before committing.

---

## 4. Safety & Security Rules

1. **Zero Secret Persistence**: Never add columns intended to store provider API keys (`OPENAI_API_KEY`, etc.) or user passwords to domain entity tables.
2. **Reversible DDL**: Every migration must implement both an `upgrade()` and a fully symmetric `downgrade()` method.
3. **Audit Immutability**: `audit_events` rows represent tamper-resistant compliance records. Normal application code must never issue updates or direct deletes against this table.
4. **Idempotency Guarantees**: Always enforce database-level uniqueness constraints for idempotency keys (`idempotency_key` on runs, `approval_token` on approvals, `content_hash` on evidence).
