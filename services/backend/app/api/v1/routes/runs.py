"""API route endpoints for research runs management."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.db.session import async_session_scope, get_async_session
from app.models.enums import ApprovalStatus, OutboxStatus, RunStatus
from app.models.outbox import OutboxEvent
from app.schemas.events import AuditEventListResponse, AuditEventResponse
from app.schemas.reports import ReportResponse
from app.schemas.runs import (
    ApprovalPendingResponse,
    EvidenceItemResponse,
    PlanSummaryResponse,
    RunCancelResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunDetailResponse,
    RunEvidenceListResponse,
    RunListResponse,
    RunSummaryResponse,
    StepCompactResponse,
)
from app.schemas.steps import RunStepListResponse, RunStepResponse
from app.services import outbox_service, run_service

router = APIRouter(prefix="/runs", tags=["Runs"])


async def _dispatch_outbox_for_run(run_id: uuid.UUID) -> None:
    """Background task to immediately dispatch committed outbox event to broker."""
    try:
        async with async_session_scope() as session:
            stmt = select(OutboxEvent).where(
                OutboxEvent.aggregate_id == str(run_id),
                OutboxEvent.status == OutboxStatus.PENDING,
            )
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()
            if event:
                await outbox_service.dispatch_outbox_event_async(session, event)
    except Exception:
        # Broker errors during background dispatch are recorded in outbox_events; do not raise.
        pass


@router.post(
    "",
    response_model=RunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new research run",
    description="Validates the research objective and enqueues an asynchronous run. Never blocks on LLM calls.",
    dependencies=[Depends(verify_api_key)],
)
async def create_run(
    request_data: RunCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> RunCreateResponse:
    """Submit a research run for background execution."""
    correlation_id = getattr(request.state, "correlation_id", None)
    run, is_new = await run_service.create_run(session, request_data, correlation_id)

    if is_new:
        background_tasks.add_task(_dispatch_outbox_for_run, run.id)

    return RunCreateResponse(
        run_id=run.id,
        status=run.status,
        created_at=run.created_at,
    )


@router.get(
    "",
    response_model=RunListResponse,
    summary="List historical research runs",
    description="Retrieves paginated list of research runs with optional status filtering.",
    dependencies=[Depends(verify_api_key)],
)
async def list_runs(
    status_filter: RunStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    session: AsyncSession = Depends(get_async_session),
) -> RunListResponse:
    """Retrieve historical runs collection."""
    items, total = await run_service.list_runs(session, status_filter, limit, offset)
    summary_items = [
        RunSummaryResponse(
            run_id=r.id,
            objective=r.objective,
            domain=r.domain,
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in items
    ]
    return RunListResponse(items=summary_items, total=total, limit=limit, offset=offset)


@router.get(
    "/{run_id}",
    response_model=RunDetailResponse,
    summary="Get research run state",
    description="Retrieves detailed state of an individual run, including plan and active gates.",
    dependencies=[Depends(verify_api_key)],
)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> RunDetailResponse:
    """Retrieve detailed state of a research run."""
    run = await run_service.get_run_by_id(session, run_id)

    plan_summary: PlanSummaryResponse | None = None
    if run.steps:
        compact_steps = [
            StepCompactResponse(
                step_id=s.id,
                step_index=s.step_index,
                step_identifier=s.step_identifier,
                title=s.title,
                tool_name=s.tool_name,
                status=s.status.value,
                requires_human_approval=s.requires_human_approval,
            )
            for s in run.steps
        ]
        plan_summary = PlanSummaryResponse(
            total_steps=len(compact_steps),
            steps=compact_steps,
        )

    approval_pending: ApprovalPendingResponse | None = None
    if run.approvals:
        pending_approval = next(
            (a for a in run.approvals if a.status == ApprovalStatus.PENDING), None
        )
        if pending_approval:
            approval_pending = ApprovalPendingResponse(
                approval_id=pending_approval.id,
                step_id=pending_approval.step_id,
                proposed_action=pending_approval.proposed_action,
            )

    return RunDetailResponse(
        run_id=run.id,
        status=run.status,
        objective=run.objective,
        domain=run.domain,
        geography=run.geography,
        llm_provider=run.llm_provider,
        search_provider=run.search_provider,
        budget_usd_limit=run.budget_usd_limit,
        estimated_cost_usd=run.estimated_cost_usd,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        plan=plan_summary,
        approval_pending=approval_pending,
    )


@router.get(
    "/{run_id}/steps",
    response_model=RunStepListResponse,
    summary="Get plan steps for a run",
    description="Lists all sequential execution steps scheduled or executed for a run.",
    dependencies=[Depends(verify_api_key)],
)
async def get_run_steps(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> RunStepListResponse:
    """Retrieve execution steps for a research run."""
    steps = await run_service.get_run_steps(session, run_id)
    step_items = [
        RunStepResponse(
            step_id=s.id,
            run_id=s.run_id,
            step_index=s.step_index,
            step_identifier=s.step_identifier,
            title=s.title,
            tool_name=s.tool_name,
            parameters=s.parameters,
            requires_human_approval=s.requires_human_approval,
            status=s.status,
            retry_count=s.retry_count,
            error_message=s.error_message,
            started_at=s.started_at,
            completed_at=s.completed_at,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in steps
    ]
    return RunStepListResponse(run_id=run_id, items=step_items, total=len(step_items))


@router.get(
    "/{run_id}/events",
    response_model=AuditEventListResponse,
    summary="Get audit event log for a run",
    description="Retrieves the immutable audit event log associated with a research run.",
    dependencies=[Depends(verify_api_key)],
)
async def get_run_events(
    run_id: uuid.UUID,
    event_type: str | None = Query(default=None, description="Filter by event type"),
    limit: int = Query(default=100, ge=1, le=200, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    session: AsyncSession = Depends(get_async_session),
) -> AuditEventListResponse:
    """Retrieve audit events for a research run."""
    events, total = await run_service.get_run_events(session, run_id, event_type, limit, offset)
    event_items = [
        AuditEventResponse(
            event_id=e.id,
            run_id=e.run_id,
            step_id=e.step_id,
            correlation_id=e.correlation_id,
            event_type=e.event_type,
            actor=e.actor,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]
    return AuditEventListResponse(
        run_id=run_id, items=event_items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/{run_id}/cancel",
    response_model=RunCancelResponse,
    summary="Cancel an active research run",
    description="Requests cancellation of an active run. Rejects terminal runs.",
    dependencies=[Depends(verify_api_key)],
)
async def cancel_run(
    run_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> RunCancelResponse:
    """Cancel an ongoing research run."""
    correlation_id = getattr(request.state, "correlation_id", None)
    run = await run_service.cancel_run(session, run_id, correlation_id)
    return RunCancelResponse(
        run_id=run.id,
        status=run.status,
        message="Run execution cancelled by operator request.",
    )


@router.get(
    "/{run_id}/report",
    response_model=ReportResponse,
    summary="Get synthesized research report",
    description="Retrieves the completed research report with citations. Returns 404 if not yet generated.",
    dependencies=[Depends(verify_api_key)],
)
async def get_run_report(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> ReportResponse:
    """Retrieve final report for a research run."""
    report = await run_service.get_run_report(session, run_id)
    return ReportResponse(
        report_id=report.id,
        run_id=report.run_id,
        title=report.title,
        markdown_content=report.markdown_content,
        executive_summary=report.executive_summary,
        citations=report.citations,
        metadata_payload=report.metadata_payload,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get(
    "/{run_id}/evidence",
    response_model=RunEvidenceListResponse,
    summary="Get captured evidence for a run",
    description="Retrieves all immutable empirical evidence snippets and source hashes captured for a run.",
    dependencies=[Depends(verify_api_key)],
)
async def get_run_evidence(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> RunEvidenceListResponse:
    """Retrieve captured evidence records for a research run."""
    items = await run_service.get_run_evidence(session, run_id)
    evidence_items = [
        EvidenceItemResponse(
            evidence_id=e.id,
            run_id=e.run_id,
            step_id=e.step_id,
            source_id=e.source_id,
            source_url=e.source_url,
            content_hash=e.content_hash,
            raw_snippet=e.raw_snippet,
            metadata_payload=e.metadata_payload,
            created_at=e.created_at,
        )
        for e in items
    ]
    return RunEvidenceListResponse(run_id=run_id, items=evidence_items, total=len(evidence_items))
