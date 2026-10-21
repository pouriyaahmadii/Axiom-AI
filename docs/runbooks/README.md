# Operational Runbooks (`docs/runbooks`)

Step-by-step operational playbooks for maintaining, troubleshooting, operating, and recovering AgentOps:
- [`local-infrastructure.md`](local-infrastructure.md): Managing Docker Compose services, healthchecks, loopback bindings, and n8n Community integration.
- [`ci-local-reproduction.md`](ci-local-reproduction.md): Guide for local reproduction of all 11 GitHub Actions CI checks, least-privilege permissions, and supply-chain security.
- [`troubleshooting.md`](troubleshooting.md): Diagnostic workflows for database connections, Celery workers, n8n webhook HMAC verification, SSRF defense triggers, and budget exhaustion.
- [`recovery.md`](recovery.md): Procedures for database restoration, worker task replay via Outbox events, stale HITL approval cleanup, and safe non-destructive state resets.
- [`backup-and-restore.md`](backup-and-restore.md): Procedures for database dumps, Redis persistence, volume backups, and safe non-destructive resets.
- [`database-migrations.md`](database-migrations.md): Authoring, verifying, executing, and rolling back Alembic database migrations.
