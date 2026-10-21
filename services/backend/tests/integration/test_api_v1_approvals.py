"""Integration tests for Human-in-the-Loop (HITL) approval endpoints (/api/v1/approvals)."""

import uuid

import pytest
from httpx import AsyncClient

from app.models import Approval, ApprovalStatus, Run, RunStatus, RunStep


@pytest.mark.integration
async def test_approve_step_success(async_client: AsyncClient, async_db_session):
    """Verify approving a gated step updates status to APPROVED and resumes parent Run."""
    run = Run(objective="Approval test run", domain="security", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_sensitive",
        title="Sensitive Action",
        tool_name="web_search",
        requires_human_approval=True,
    )
    async_db_session.add(step)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        step_id=step.id,
        approval_token="tok_test_approval_123",
        status=ApprovalStatus.PENDING,
        proposed_action={"tool": "web_search", "query": "sensitive search"},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # Approve step
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"operator_notes": "Action approved by analyst."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_id"] == str(approval.id)
    assert data["status"] == "APPROVED"
    assert data["run_status"] == "RUNNING"
    assert data["operator_notes"] == "Action approved by analyst."
    assert data["resolved_at"] is not None


@pytest.mark.integration
async def test_reject_step_with_abort(async_client: AsyncClient, async_db_session):
    """Verify rejecting a gated step aborts the run when abort_run=True."""
    run = Run(objective="Rejection test run", domain="security", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_sensitive",
        title="Sensitive Action",
        tool_name="web_search",
        requires_human_approval=True,
    )
    async_db_session.add(step)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        step_id=step.id,
        approval_token="tok_test_rejection_123",
        status=ApprovalStatus.PENDING,
        proposed_action={"tool": "web_search", "query": "risky query"},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # Reject step
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/reject",
        json={"operator_notes": "Too risky to proceed.", "abort_run": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_id"] == str(approval.id)
    assert data["status"] == "REJECTED"
    assert data["run_status"] == "ABORTED_BY_OPERATOR"


@pytest.mark.integration
async def test_approval_already_resolved_conflict(async_client: AsyncClient, async_db_session):
    """Verify attempting to approve an already-approved request fails with 409 Conflict."""
    run = Run(objective="Double approval run", domain="security")
    async_db_session.add(run)
    await async_db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_sensitive",
        title="Sensitive Step",
        tool_name="web_search",
        requires_human_approval=True,
    )
    async_db_session.add(step)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        step_id=step.id,
        approval_token="tok_resolved_test",
        status=ApprovalStatus.APPROVED,  # Already resolved
        proposed_action={"tool": "web_search"},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # Conflict: attempting to reject an already-approved request fails with 409 Conflict
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/reject",
        json={"operator_notes": "Trying to reject already approved gate"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.integration
async def test_approval_not_found(async_client: AsyncClient):
    """Verify 404 response for non-existent approval request."""
    unknown_id = str(uuid.uuid4())
    response = await async_client.post(
        f"/api/v1/approvals/{unknown_id}/approve",
        json={"operator_notes": "Notes"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
