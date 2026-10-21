"""API route endpoints for Human-in-the-Loop (HITL) approval gates."""

from __future__ import annotations

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


def _extract_operator_identity(request: Request, api_key: str) -> str:
    """Extract authenticated operator identity from headers or API key caller."""
    operator_header = request.headers.get("X-Operator-Id") or request.headers.get("X-Actor")
    if operator_header:
        return operator_header.strip()
    return f"key:{api_key[:8]}" if api_key != "local-dev-loopback" else "operator-local"


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a gated execution checkpoint",
    description="Submits an approval verdict to resume a paused research run idempotently.",
)
async def approve_step(
    approval_id: uuid.UUID,
    payload: ApprovalActionRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_async_session),
) -> ApprovalResponse:
    """Approve a gated plan, step, or report checkpoint."""
    correlation_id = getattr(request.state, "correlation_id", None)
    operator = _extract_operator_identity(request, api_key)

    approval, run = await approval_service.approve_step(
        session=session,
        approval_id=approval_id,
        operator_notes=payload.operator_notes,
        expected_payload_hash=payload.expected_payload_hash,
        resolved_by=operator,
        correlation_id=correlation_id,
    )
    return ApprovalResponse(
        approval_id=approval.id,
        run_id=approval.run_id,
        step_id=approval.step_id,
        action=approval.action,
        payload_hash=approval.payload_hash,
        version=approval.version,
        status=approval.status,
        proposed_action=approval.proposed_action,
        operator_notes=approval.operator_notes,
        resolved_by=approval.resolved_by,
        expires_at=approval.expires_at,
        resolved_at=approval.resolved_at,
        run_status=run.status,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a gated execution checkpoint",
    description="Submits a rejection verdict with documented rationale, optionally aborting the run.",
)
async def reject_step(
    approval_id: uuid.UUID,
    payload: ApprovalRejectRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_async_session),
) -> ApprovalResponse:
    """Reject a gated plan, step, or report checkpoint with a reason."""
    correlation_id = getattr(request.state, "correlation_id", None)
    operator = _extract_operator_identity(request, api_key)

    approval, run = await approval_service.reject_step(
        session=session,
        approval_id=approval_id,
        operator_notes=payload.operator_notes,
        abort_run=payload.abort_run,
        resolved_by=operator,
        correlation_id=correlation_id,
    )
    return ApprovalResponse(
        approval_id=approval.id,
        run_id=approval.run_id,
        step_id=approval.step_id,
        action=approval.action,
        payload_hash=approval.payload_hash,
        version=approval.version,
        status=approval.status,
        proposed_action=approval.proposed_action,
        operator_notes=approval.operator_notes,
        resolved_by=approval.resolved_by,
        expires_at=approval.expires_at,
        resolved_at=approval.resolved_at,
        run_status=run.status,
    )
