# Operational Runbooks (`docs/runbooks`)

Step-by-step operational playbooks for maintaining, troubleshooting, and operating AgentOps:
- [`local-infrastructure.md`](local-infrastructure.md): Managing Docker Compose services, healthchecks, loopback bindings, and n8n Community integration.
- [`backup-and-restore.md`](backup-and-restore.md): Procedures for database dumps, Redis persistence, volume backups, and safe non-destructive resets.
- `local-development.md`: Setting up, running, and debugging the local stack.
- `database-migrations.md`: Authoring and applying Alembic database migrations.
- `incident-recovery.md`: Recovering stuck or aborted runs and inspecting Celery worker health.
