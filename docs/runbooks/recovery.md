# Operational Disaster Recovery & Remediation Runbook (`docs/runbooks/recovery.md`)

This runbook establishes standard operating procedures for recovering AgentOps services, state machines, message brokers, and relational databases from catastrophic crashes, corrupted states, broker partitions, and stale approvals.

---

## 1. Recovery Objectives & Principles

| Metric | Target Objective | Implementation Mechanism |
| :--- | :--- | :--- |
| **Recovery Time Objective (RTO)** | $< 15\text{ minutes}$ | Automated Docker Compose healthchecks and scripted database restore |
| **Recovery Point Objective (RPO)** | $< 5\text{ minutes}$ | Transactional Outbox pattern, periodic WAL persistence, and PostgreSQL checkpointing |
| **Data Integrity Guarantee** | Zero partial writes | Relational database transactions with explicit foreign keys and immutable audit logs |
| **Execution State Guarantee** | At-least-once with idempotency | LangGraph durable checkpointing and idempotent run creation keys |

---

## 2. Database Disaster Recovery & Restoration

### Scenario 2.1: Full Database Restoration from Backup
When the PostgreSQL primary volume is corrupted or catastrophically lost:

```bash
# 1. Stop all consuming application services to halt write traffic
docker compose -p agentops stop api worker web n8n

# 2. Verify PostgreSQL container is running in isolated maintenance mode
docker compose -p agentops up -d postgres

# 3. Locate the latest verified SQL dump file
BACKUP_FILE=$(ls -t backups/agentops_db_*.sql.gz 2>/dev/null | head -n 1)
echo "Restoring from: ${BACKUP_FILE}"

# 4. Drop and recreate the agentops_db database
docker compose -p agentops exec -T postgres psql -U agentops_user -d postgres << 'EOF'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'agentops_db';
DROP DATABASE IF EXISTS agentops_db;
CREATE DATABASE agentops_db OWNER agentops_user;
EOF

# 5. Stream the compressed backup into the fresh database
gunzip -c "${BACKUP_FILE}" | docker compose -p agentops exec -T postgres psql -U agentops_user -d agentops_db

# 6. Verify Alembic schema migration state
source .venv/bin/activate
cd services/backend
alembic current

# 7. Restart the full service suite
docker compose -p agentops start api worker web n8n
```

### Scenario 2.2: Resolving Corrupted Alembic Migration State
If a deployment failed mid-migration, leaving Alembic in an inconsistent version state:

```bash
# Inspect current version table
docker compose -p agentops exec postgres psql -U agentops_user -d agentops_db \
  -c "SELECT version_num FROM alembic_version;"

# If the database schema matches a known revision but alembic_version is desynchronized:
alembic stamp <target_revision_hash>

# Validate schema alignment without executing DDL
alembic check
```

---

## 3. Worker & Broker State Recovery

### Scenario 3.1: Resuming Crashed Worker Runs via LangGraph Checkpoints
If a Celery worker is abruptly terminated during a research run, the run remains in `RUNNING` or `STEP_EXECUTING` state in PostgreSQL.

AgentOps employs durable LangGraph checkpoints persisted to PostgreSQL after every node transition.

```bash
# 1. Identify interrupted runs that have been silent for > 5 minutes
source .venv/bin/activate
python - << 'EOF'
import asyncio
from services.backend.app.core.database import async_session_factory
from services.backend.app.repositories.run_repository import RunRepository
from services.backend.app.schemas.run import RunStatus

async def identify_orphaned_runs():
    async with async_session_factory() as session:
        repo = RunRepository(session)
        interrupted = await repo.get_stuck_runs(timeout_seconds=300)
        print(f"Found {len(interrupted)} orphaned runs:")
        for r in interrupted:
            print(f"  - Run ID: {r.id} (Status: {r.status}, Last Step: {r.current_step})")

asyncio.run(identify_orphaned_runs())
EOF

# 2. Resubmit the run continuation task to Celery
python - << 'EOF'
import sys
from services.backend.app.workers.tasks import resume_agent_run

# Trigger safe continuation from the last valid PostgreSQL checkpoint
run_id = "70cf52eb-72e0-4ea4-abbf-a0377e565683"
resume_agent_run.delay(run_id=run_id)
print(f"Resumption task enqueued for Run {run_id}")
EOF
```

### Scenario 3.2: Replaying Unprocessed Outbox Events
When Redis fails or experiences message loss, the durable PostgreSQL `outbox_events` table ensures zero lost domain events:

```bash
# Scan for unpublished or pending Outbox events and re-dispatch them
python - << 'EOF'
import asyncio
from services.backend.app.core.database import async_session_factory
from services.backend.app.services.outbox_service import OutboxService

async def replay_outbox():
    async with async_session_factory() as session:
        outbox = OutboxService(session)
        replayed = await outbox.publish_pending_events()
        print(f"Successfully replayed {replayed} Outbox events to message broker")

asyncio.run(replay_outbox())
EOF
```

### Scenario 3.3: Draining Poisoned Queue Messages
If a malformed task causes worker crash loops (crash-on-dequeue):

```bash
# Purge tasks from the Celery queue
docker compose -p agentops exec redis redis-cli DEL agentops_tasks

# Restart Celery workers with clean state
docker compose -p agentops restart worker
```

---

## 4. Human-in-the-Loop (HITL) Approval Recovery

### Scenario 4.1: Cleaning Stale Approvals (> 24 Hours)
Approval requests that exceed the operational timeout policy ($24\text{ hours}$) must be transitioned to `EXPIRED` to prevent stale execution authorization:

```bash
# Execute automated approval expiration sweep
python - << 'EOF'
import asyncio
from services.backend.app.core.database import async_session_factory
from services.backend.app.services.approval_service import ApprovalService

async def expire_stale_approvals():
    async with async_session_factory() as session:
        service = ApprovalService(session)
        expired_count = await service.expire_stale_requests(max_age_hours=24)
        print(f"Expired {expired_count} stale approval requests")

asyncio.run(expire_stale_approvals())
EOF
```

### Scenario 4.2: Handling Action Payload Drift
If an approval request payload does not match the active step payload (e.g., plan modified after approval creation), the submission is rejected with `ApprovalPayloadMismatchError`.
- **Action**: Reject the stale approval with reason: `Payload drift detected; request invalidated.`
- **Remediation**: Allow the agent to re-emit an approval checkpoint with the updated plan hash.

---

## 5. Graceful Rollback Playbook

When a new code release or migration introduces an unrecoverable defect:

### Step 1: Revert Code Revision
```bash
# Checkout previous stable release tag
git checkout v0.9.0

# Reinstall pinned dependencies
pip install -e ".[dev]"
npm --prefix apps/web ci
```

### Step 2: Downgrade Database Schema
```bash
cd services/backend
# Rollback the last migration
alembic downgrade -1

# Confirm current revision
alembic current
```

### Step 3: Rebuild and Restart Containers
```bash
docker compose -p agentops up -d --build
docker compose -p agentops ps
```

---

## 6. Non-Destructive State Reset Procedure

When preparing the development environment for a clean demonstration without wiping database schemas, user roles, or Docker configurations:

```bash
# Truncate transactional run tables while preserving schema and configuration
docker compose -p agentops exec -T postgres psql -U agentops_user -d agentops_db << 'EOF'
BEGIN;
TRUNCATE TABLE audit_events CASCADE;
TRUNCATE TABLE outbox_events CASCADE;
TRUNCATE TABLE llm_calls CASCADE;
TRUNCATE TABLE tool_invocations CASCADE;
TRUNCATE TABLE evidence_items CASCADE;
TRUNCATE TABLE approvals CASCADE;
TRUNCATE TABLE reports CASCADE;
TRUNCATE TABLE run_steps CASCADE;
TRUNCATE TABLE graph_checkpoints CASCADE;
TRUNCATE TABLE sources CASCADE;
TRUNCATE TABLE runs CASCADE;
COMMIT;
EOF

# Flush Redis broker and caches
docker compose -p agentops exec redis redis-cli FLUSHALL

# Reset in-memory document caches and restart workers
docker compose -p agentops restart api worker
echo "Clean transactional state reset complete. Ready for new demonstration."
```

---

## 7. Post-Recovery Verification Checklist

After executing any recovery procedure, verify:
- [ ] API readiness probe returns `200 OK` (`curl -s http://127.0.0.1:8000/health`).
- [ ] Celery worker responds to ping (`celery inspect ping`).
- [ ] Database query latency is within SLA ($\le 2.5\text{ ms}$).
- [ ] Next.js dashboard loads successfully without proxy errors (`http://127.0.0.1:3000`).
- [ ] Submit a test mock run to verify the full end-to-end pipeline.
