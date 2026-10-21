"""Business service layer for research run execution lifecycle and state management."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError
from app.models import (
    AuditEvent,
    AuditEventType,
    EvidenceItem,
    OutboxEvent,
    Report,
    Run,
    RunStatus,
    RunStep,
)
from app.schemas.runs import RunCreateRequest

settings = get_settings()

ACTIVE_RUN_STATUSES = {
    RunStatus.QUEUED,
    RunStatus.PLANNING,
    RunStatus.RUNNING,
    RunStatus.AWAITING_APPROVAL,
}


async def create_run(
    session: AsyncSession,
    request: RunCreateRequest,
    correlation_id: str | None = None,
) -> tuple[Run, bool]:
    """Create a new research run or return an existing run if idempotent match exists.

    Returns:
        tuple[Run, bool]: (Run instance, is_new_run boolean).
    """
    # 1. Check idempotency if key provided
    if request.idempotency_key:
        stmt = select(Run).where(Run.idempotency_key == request.idempotency_key)
        result = await session.execute(stmt)
        existing_run = result.scalar_one_or_none()

        if existing_run:
            if existing_run.objective != request.objective:
                raise ConflictError(
                    f"Idempotency key '{request.idempotency_key}' was previously used for a different objective."
                )
            return existing_run, False

    # 2. Extract provider selections
    llm_provider = settings.LLM_PROVIDER
    search_provider = settings.SEARCH_PROVIDER
    if request.provider_override:
        llm_provider = request.provider_override.get("llm", llm_provider)
        search_provider = request.provider_override.get("search", search_provider)

    # 3. Create run record
    run = Run(
        id=uuid.uuid4(),
        objective=request.objective,
        domain=request.domain,
        geography=request.geography,
        status=RunStatus.QUEUED,
        llm_provider=llm_provider,
        search_provider=search_provider,
        budget_usd_limit=Decimal(str(settings.BUDGET_USD_LIMIT)),
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_key=request.idempotency_key,
        correlation_id=correlation_id,
    )
    session.add(run)

    # 4. Record audit event
    audit_event = AuditEvent(
        run_id=run.id,
        correlation_id=correlation_id,
        event_type=AuditEventType.RUN_QUEUED.value,
        actor="api_client",
        payload={
            "objective": run.objective,
            "domain": run.domain,
            "llm_provider": run.llm_provider,
            "search_provider": run.search_provider,
        },
    )
    session.add(audit_event)

    # 5. Create outbox event for reliable asynchronous background pickup
    outbox_event = OutboxEvent(
        event_type="RUN_QUEUED",
        aggregate_type="run",
        aggregate_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "status": run.status.value,
            "objective": run.objective,
            "correlation_id": correlation_id,
        },
    )
    session.add(outbox_event)

    try:
        await session.flush()
        await session.refresh(run)
        return run, True
    except IntegrityError as err:
        if request.idempotency_key:
            await session.rollback()
            stmt = select(Run).where(Run.idempotency_key == request.idempotency_key)
            result = await session.execute(stmt)
            existing_run = result.scalar_one_or_none()
            if existing_run:
                if existing_run.objective != request.objective:
                    raise ConflictError(
                        f"Idempotency key '{request.idempotency_key}' was previously used for a different objective."
                    ) from err
                return existing_run, False
        raise


async def list_runs(
    session: AsyncSession,
    status: RunStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Run], int]:
    """Retrieve paginated collection of historical runs with optional status filtering."""
    base_query = select(Run)
    count_query = select(func.count()).select_from(Run)

    if status:
        base_query = base_query.where(Run.status == status)
        count_query = count_query.where(Run.status == status)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    items_stmt = base_query.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    items_result = await session.execute(items_stmt)
    items = list(items_result.scalars().all())

    return items, total


async def get_run_by_id(session: AsyncSession, run_id: uuid.UUID) -> Run:
    """Retrieve detailed state of a run by its UUID."""
    stmt = (
        select(Run)
        .where(Run.id == run_id)
        .options(
            selectinload(Run.steps),
            selectinload(Run.approvals),
        )
    )
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise NotFoundError(f"Run with ID '{run_id}' not found.")
    return run


async def get_run_steps(session: AsyncSession, run_id: uuid.UUID) -> list[RunStep]:
    """Retrieve execution plan steps for a given run."""
    # Ensure run exists
    await get_run_by_id(session, run_id)

    stmt = select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_index.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_run_events(
    session: AsyncSession,
    run_id: uuid.UUID,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """Retrieve immutable audit event trail for a run."""
    # Ensure run exists
    await get_run_by_id(session, run_id)

    base_query = select(AuditEvent).where(AuditEvent.run_id == run_id)
    count_query = select(func.count()).select_from(AuditEvent).where(AuditEvent.run_id == run_id)

    if event_type:
        base_query = base_query.where(AuditEvent.event_type == event_type)
        count_query = count_query.where(AuditEvent.event_type == event_type)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    stmt = base_query.order_by(AuditEvent.created_at.asc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def cancel_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    correlation_id: str | None = None,
) -> Run:
    """Cancel an active run, validating that it is in a cancellable state."""
    run = await get_run_by_id(session, run_id)

    if run.status not in ACTIVE_RUN_STATUSES:
        raise InvalidStateTransitionError(
            f"Cannot cancel run in terminal '{run.status.value}' state. "
            f"Only active runs ({', '.join(s.value for s in ACTIVE_RUN_STATUSES)}) can be cancelled."
        )

    previous_status = run.status.value
    run.status = RunStatus.CANCELLED
    run.completed_at = datetime.now(timezone.utc)

    # Record cancellation audit event
    audit_event = AuditEvent(
        run_id=run.id,
        correlation_id=correlation_id,
        event_type="RUN_CANCELLED",
        actor="operator",
        payload={
            "previous_status": previous_status,
            "new_status": RunStatus.CANCELLED.value,
            "reason": "Operator cancellation request",
        },
    )
    session.add(audit_event)

    await session.flush()
    return run


async def get_run_report(session: AsyncSession, run_id: uuid.UUID) -> Report:
    """Retrieve final synthesized report for a run."""
    # Ensure run exists
    await get_run_by_id(session, run_id)

    stmt = select(Report).where(Report.run_id == run_id)
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise NotFoundError(f"Report has not been synthesized yet for run '{run_id}'.")
    return report


async def get_run_evidence(session: AsyncSession, run_id: uuid.UUID) -> list[EvidenceItem]:
    """Retrieve immutable empirical evidence records for a research run."""
    # Ensure run exists
    await get_run_by_id(session, run_id)

    stmt = (
        select(EvidenceItem)
        .where(EvidenceItem.run_id == run_id)
        .order_by(EvidenceItem.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
