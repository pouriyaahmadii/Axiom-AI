"""Recovery and reconciliation service for discovering and resolving interrupted work."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.enums import AuditEventType, RunStatus, StepStatus
from app.models.run import Run
from app.models.step import RunStep
from app.services.outbox_service import dispatch_pending_outbox_sync

logger = structlog.get_logger(__name__)

INTERRUPTIBLE_STATUSES = {
    RunStatus.PLANNING,
    RunStatus.RUNNING,
}


def reconcile_interrupted_runs(
    session: Session,
    stale_threshold_seconds: int = 300,
) -> int:
    """Discover and safely transition stale or abandoned runs left by terminated workers.

    A run in PLANNING or RUNNING status whose last update exceeds the stale threshold
    indicates an ungraceful worker termination (e.g. SIGKILL, OOM, power loss).
    This function reconciles the database state to prevent zombie active statuses.

    Returns:
        int: Number of reconciled runs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)

    stmt = select(Run).where(
        Run.status.in_(INTERRUPTIBLE_STATUSES),
        Run.updated_at < cutoff,
    )
    stale_runs = session.execute(stmt).scalars().all()
    reconciled_count = 0

    for run in stale_runs:
        original_status = run.status
        run.status = RunStatus.FAILED
        run.error_message = (
            f"Execution interrupted: worker process lost or terminated unexpectedly while in {original_status.value} "
            f"state. Safely reconciled at {datetime.now(timezone.utc).isoformat()}."
        )
        run.completed_at = datetime.now(timezone.utc)

        # Mark any active in-flight step as FAILED
        step_stmt = select(RunStep).where(
            RunStep.run_id == run.id,
            RunStep.status == StepStatus.RUNNING,
        )
        active_steps = session.execute(step_stmt).scalars().all()
        for step in active_steps:
            step.status = StepStatus.FAILED
            step.error_message = "Step interrupted by worker process termination."
            step.completed_at = datetime.now(timezone.utc)

        # Add audit trail entry
        audit_event = AuditEvent(
            run_id=run.id,
            correlation_id=run.correlation_id,
            event_type=AuditEventType.RUN_FAILED.value,
            actor="recovery_service",
            payload={
                "reason": "worker_interruption_reconciliation",
                "previous_status": original_status.value,
                "reconciled_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(audit_event)
        session.flush()

        logger.warning(
            "run_interruption_reconciled",
            run_id=str(run.id),
            previous_status=original_status.value,
            cutoff_seconds=stale_threshold_seconds,
        )
        reconciled_count += 1

    return reconciled_count


def run_startup_recovery(session: Session) -> dict[str, int]:
    """Execute complete reconciliation and outbox sweeper on worker or API startup."""
    reconciled_runs = reconcile_interrupted_runs(session)
    published_outbox, failed_outbox = dispatch_pending_outbox_sync(session)

    logger.info(
        "startup_recovery_completed",
        reconciled_runs=reconciled_runs,
        published_outbox=published_outbox,
        failed_outbox=failed_outbox,
    )
    return {
        "reconciled_runs": reconciled_runs,
        "published_outbox": published_outbox,
        "failed_outbox": failed_outbox,
    }
