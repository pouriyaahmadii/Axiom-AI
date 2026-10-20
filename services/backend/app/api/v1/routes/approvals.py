"""API route endpoints for Human-in-the-Loop (HITL) approval gates."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.db.session import get_async_session
from app.schemas.approvals import (
    ApprovalActionRequest,
    ApprovalRejectRequest,
    ApprovalResponse,
)
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a gated execution step",
    description="Submits an approval verdict to resume a paused research run.",
    dependencies=[Depends(verify_api_key)],
)
async def approve_step(
    approval_id: uuid.UUID,
    payload: ApprovalActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ApprovalResponse:
    """Approve a gated plan step."""
    correlation_id = getattr(request.state, "correlation_id", None)
    approval, run = await approval_service.approve_step(
        session,
        approval_id,
        payload.operator_notes,
        correlation_id,
    )
    return ApprovalResponse(
        approval_id=approval.id,
        run_id=approval.run_id,
        step_id=approval.step_id,
        status=approval.status,
        proposed_action=approval.proposed_action,
        operator_notes=approval.operator_notes,
        resolved_at=approval.resolved_at,
        run_status=run.status,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a gated execution step",
    description="Submits a rejection verdict, optionally aborting the associated run.",
    dependencies=[Depends(verify_api_key)],
)
async def reject_step(
    approval_id: uuid.UUID,
    payload: ApprovalRejectRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ApprovalResponse:
    """Reject a gated plan step."""
    correlation_id = getattr(request.state, "correlation_id", None)
    approval, run = await approval_service.reject_step(
        session,
        approval_id,
        payload.operator_notes,
        payload.abort_run,
        correlation_id,
    )
    return ApprovalResponse(
        approval_id=approval.id,
        run_id=approval.run_id,
        step_id=approval.step_id,
        status=approval.status,
        proposed_action=approval.proposed_action,
        operator_notes=approval.operator_notes,
        resolved_at=approval.resolved_at,
        run_status=run.status,
    )
