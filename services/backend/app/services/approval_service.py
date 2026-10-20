"""Business service layer for Human-in-the-Loop (HITL) approval gates."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.models import (
    Approval,
    ApprovalStatus,
    AuditEvent,
    AuditEventType,
    OutboxEvent,
    Run,
    RunStatus,
)


async def approve_step(
    session: AsyncSession,
    approval_id: uuid.UUID,
    operator_notes: str | None = None,
    correlation_id: str | None = None,
) -> tuple[Approval, Run]:
    """Approve a gated execution step and resume the associated research run."""
    stmt = select(Approval).where(Approval.id == approval_id)
    result = await session.execute(stmt)
    approval = result.scalar_one_or_none()

    if not approval:
        raise NotFoundError(f"Approval request with ID '{approval_id}' not found.")

    if approval.status != ApprovalStatus.PENDING:
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has already been resolved with status '{approval.status.value}'."
        )

    # 1. Update approval state
    approval.status = ApprovalStatus.APPROVED
    approval.operator_notes = operator_notes
    approval.resolved_at = datetime.now(timezone.utc)

    # 2. Update parent run state to resume execution
    run_stmt = select(Run).where(Run.id == approval.run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one()

    if run.status == RunStatus.AWAITING_APPROVAL:
        run.status = RunStatus.RUNNING

    # 3. Log audit event
    audit_event = AuditEvent(
        run_id=run.id,
        step_id=approval.step_id,
        correlation_id=correlation_id,
        event_type=AuditEventType.APPROVAL_RESOLVED.value,
        actor="operator",
        payload={
            "verdict": "approved",
            "approval_id": str(approval.id),
            "operator_notes": operator_notes,
        },
    )
    session.add(audit_event)

    # 4. Enqueue outbox event for agent runtime resumption
    outbox_event = OutboxEvent(
        event_type="APPROVAL_APPROVED",
        aggregate_type="approval",
        aggregate_id=str(approval.id),
        payload={
            "approval_id": str(approval.id),
            "run_id": str(run.id),
            "step_id": str(approval.step_id),
            "status": "APPROVED",
        },
    )
    session.add(outbox_event)

    await session.flush()
    return approval, run


async def reject_step(
    session: AsyncSession,
    approval_id: uuid.UUID,
    operator_notes: str | None = None,
    abort_run: bool = True,
    correlation_id: str | None = None,
) -> tuple[Approval, Run]:
    """Reject a gated execution step, optionally aborting the entire research run."""
    stmt = select(Approval).where(Approval.id == approval_id)
    result = await session.execute(stmt)
    approval = result.scalar_one_or_none()

    if not approval:
        raise NotFoundError(f"Approval request with ID '{approval_id}' not found.")

    if approval.status != ApprovalStatus.PENDING:
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has already been resolved with status '{approval.status.value}'."
        )

    # 1. Update approval state
    approval.status = ApprovalStatus.REJECTED
    approval.operator_notes = operator_notes
    approval.resolved_at = datetime.now(timezone.utc)

    # 2. Update parent run state
    run_stmt = select(Run).where(Run.id == approval.run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one()

    if abort_run:
        run.status = RunStatus.ABORTED_BY_OPERATOR
        run.completed_at = datetime.now(timezone.utc)

    # 3. Log audit event
    audit_event = AuditEvent(
        run_id=run.id,
        step_id=approval.step_id,
        correlation_id=correlation_id,
        event_type=AuditEventType.APPROVAL_RESOLVED.value,
        actor="operator",
        payload={
            "verdict": "rejected",
            "abort_run": abort_run,
            "approval_id": str(approval.id),
            "operator_notes": operator_notes,
        },
    )
    session.add(audit_event)

    # 4. Enqueue outbox event
    outbox_event = OutboxEvent(
        event_type="APPROVAL_REJECTED",
        aggregate_type="approval",
        aggregate_id=str(approval.id),
        payload={
            "approval_id": str(approval.id),
            "run_id": str(run.id),
            "step_id": str(approval.step_id),
            "status": "REJECTED",
            "abort_run": abort_run,
        },
    )
    session.add(outbox_event)

    await session.flush()
    return approval, run
