"""Business service layer for Human-in-the-Loop (HITL) approval gates."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.core.security import generate_secure_token
from app.models import (
    Approval,
    ApprovalStatus,
    AuditEvent,
    AuditEventType,
    OutboxEvent,
    Run,
    RunStatus,
)

settings = get_settings()


async def create_approval_request(
    session: AsyncSession,
    run_id: uuid.UUID,
    action: str,
    proposed_action: dict[str, Any],
    step_id: uuid.UUID | None = None,
    expires_in_seconds: int | None = None,
    correlation_id: str | None = None,
) -> Approval:
    """Create and persist a new approval request gating an execution checkpoint."""
    payload_hash = Approval.compute_payload_hash(proposed_action)
    token = generate_secure_token()
    timeout = expires_in_seconds or settings.APPROVAL_TIMEOUT_SECONDS
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout)

    approval = Approval(
        run_id=run_id,
        step_id=step_id,
        action=action,
        payload_hash=payload_hash,
        version=1,
        approval_token=token,
        status=ApprovalStatus.PENDING,
        proposed_action=proposed_action,
        expires_at=expires_at,
    )
    session.add(approval)

    # Transition run to AWAITING_APPROVAL
    run_stmt = select(Run).where(Run.id == run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one_or_none()
    if run:
        run.status = RunStatus.AWAITING_APPROVAL

    # Log audit event
    session.add(
        AuditEvent(
            run_id=run_id,
            step_id=step_id,
            correlation_id=correlation_id,
            event_type=AuditEventType.APPROVAL_REQUESTED.value,
            actor="agent_runtime",
            payload={
                "action": action,
                "payload_hash": payload_hash,
                "expires_at": expires_at.isoformat(),
            },
        )
    )

    # Log outbox event
    session.add(
        OutboxEvent(
            event_type="APPROVAL_REQUESTED",
            aggregate_type="approval",
            aggregate_id=str(approval.id),
            payload={
                "approval_id": str(approval.id),
                "run_id": str(run_id),
                "action": action,
                "step_id": str(step_id) if step_id else None,
                "payload_hash": payload_hash,
            },
        )
    )

    await session.flush()
    return approval


async def approve_step(
    session: AsyncSession,
    approval_id: uuid.UUID,
    operator_notes: str | None = None,
    expected_payload_hash: str | None = None,
    resolved_by: str | None = None,
    correlation_id: str | None = None,
) -> tuple[Approval, Run]:
    """Approve a gated execution action idempotently and resume the associated research run."""
    stmt = select(Approval).where(Approval.id == approval_id)
    result = await session.execute(stmt)
    approval = result.scalar_one_or_none()

    if not approval:
        raise NotFoundError(f"Approval request with ID '{approval_id}' not found.")

    # 1. Idempotency Check: if already approved, return without error
    run_stmt = select(Run).where(Run.id == approval.run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one()

    if approval.status == ApprovalStatus.APPROVED:
        return approval, run

    # 2. State conflict check: cannot approve an already rejected or cancelled gate
    if approval.status == ApprovalStatus.REJECTED:
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has already been rejected and cannot be approved."
        )

    # 3. Expiration / Timeout Check (Requirement 11)
    if approval.is_expired():
        approval.status = ApprovalStatus.EXPIRED
        session.add(
            AuditEvent(
                run_id=run.id,
                step_id=approval.step_id,
                correlation_id=correlation_id,
                event_type=AuditEventType.APPROVAL_RESOLVED.value,
                actor=resolved_by or "system",
                payload={
                    "verdict": "expired",
                    "approval_id": str(approval.id),
                    "action": approval.action,
                    "expired_at": approval.expires_at.isoformat() if approval.expires_at else None,
                },
            )
        )
        await session.commit()
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has expired at {approval.expires_at} and cannot be authorized."
        )

    # 4. Stale Action Payload Check (Requirement 4: Prevent stale approval authorizing changed payload)
    if (
        expected_payload_hash
        and approval.payload_hash
        and expected_payload_hash != approval.payload_hash
    ):
        raise InvalidStateTransitionError(
            f"Stale approval error: expected payload hash '{expected_payload_hash}' does not match registered payload hash '{approval.payload_hash}'."
        )

    # 5. Update approval state
    approval.status = ApprovalStatus.APPROVED
    approval.operator_notes = operator_notes
    approval.resolved_by = resolved_by or "operator"
    approval.resolved_at = datetime.now(timezone.utc)

    # 6. Update parent run state to resume execution
    if run.status == RunStatus.AWAITING_APPROVAL:
        run.status = RunStatus.RUNNING

    # 7. Log audit event
    audit_event = AuditEvent(
        run_id=run.id,
        step_id=approval.step_id,
        correlation_id=correlation_id,
        event_type=AuditEventType.APPROVAL_RESOLVED.value,
        actor=approval.resolved_by,
        payload={
            "verdict": "approved",
            "action": approval.action,
            "approval_id": str(approval.id),
            "payload_hash": approval.payload_hash,
            "operator_notes": operator_notes,
            "resolved_by": approval.resolved_by,
        },
    )
    session.add(audit_event)

    # 8. Enqueue outbox event for agent runtime resumption
    outbox_event = OutboxEvent(
        event_type="APPROVAL_APPROVED",
        aggregate_type="approval",
        aggregate_id=str(approval.id),
        payload={
            "approval_id": str(approval.id),
            "run_id": str(run.id),
            "action": approval.action,
            "step_id": str(approval.step_id) if approval.step_id else None,
            "payload_hash": approval.payload_hash,
            "status": "APPROVED",
            "verdict": "approved",
            "operator_notes": operator_notes,
            "resolved_by": approval.resolved_by,
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
    resolved_by: str | None = None,
    correlation_id: str | None = None,
) -> tuple[Approval, Run]:
    """Reject a gated execution action idempotently with a documented reason."""
    stmt = select(Approval).where(Approval.id == approval_id)
    result = await session.execute(stmt)
    approval = result.scalar_one_or_none()

    if not approval:
        raise NotFoundError(f"Approval request with ID '{approval_id}' not found.")

    run_stmt = select(Run).where(Run.id == approval.run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one()

    # 1. Idempotency Check: if already rejected, return without error
    if approval.status == ApprovalStatus.REJECTED:
        return approval, run

    # 2. State conflict check: cannot reject an already approved action
    if approval.status == ApprovalStatus.APPROVED:
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has already been approved and cannot be rejected."
        )

    # 3. Expiration Check
    if approval.is_expired():
        approval.status = ApprovalStatus.EXPIRED
        await session.flush()
        raise InvalidStateTransitionError(
            f"Approval request '{approval_id}' has expired and cannot be resolved."
        )

    # 4. Update approval state
    approval.status = ApprovalStatus.REJECTED
    approval.operator_notes = operator_notes
    approval.resolved_by = resolved_by or "operator"
    approval.resolved_at = datetime.now(timezone.utc)

    # 5. Update parent run state
    if abort_run:
        run.status = RunStatus.ABORTED_BY_OPERATOR
        run.completed_at = datetime.now(timezone.utc)
    else:
        # If not aborting the run, resume with skipped action
        if run.status == RunStatus.AWAITING_APPROVAL:
            run.status = RunStatus.RUNNING

    # 6. Log audit event
    audit_event = AuditEvent(
        run_id=run.id,
        step_id=approval.step_id,
        correlation_id=correlation_id,
        event_type=AuditEventType.APPROVAL_RESOLVED.value,
        actor=approval.resolved_by,
        payload={
            "verdict": "rejected",
            "action": approval.action,
            "abort_run": abort_run,
            "approval_id": str(approval.id),
            "payload_hash": approval.payload_hash,
            "rejection_reason": operator_notes,
            "resolved_by": approval.resolved_by,
        },
    )
    session.add(audit_event)

    # 7. Enqueue outbox event
    outbox_event = OutboxEvent(
        event_type="APPROVAL_REJECTED",
        aggregate_type="approval",
        aggregate_id=str(approval.id),
        payload={
            "approval_id": str(approval.id),
            "run_id": str(run.id),
            "action": approval.action,
            "step_id": str(approval.step_id) if approval.step_id else None,
            "status": "REJECTED",
            "verdict": "rejected",
            "abort_run": abort_run,
            "rejection_reason": operator_notes,
            "resolved_by": approval.resolved_by,
        },
    )
    session.add(outbox_event)

    await session.flush()
    return approval, run
