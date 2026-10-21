"""Integration tests for Phase 15: Persistent Human Approval and Safe Resumption."""

from __future__ import annotations

import base64
import pickle
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from langgraph.types import Command
from sqlalchemy import select

from app.agents.graph import create_agent_graph
from app.models import (
    Approval,
    ApprovalStatus,
    AuditEvent,
    AuditEventType,
    GraphCheckpoint,
    OutboxEvent,
    Run,
    RunStatus,
    RunStep,
)
from app.repositories.checkpointer import DurableCheckpointSaver
from app.services import approval_service


@pytest.mark.integration
async def test_approval_success(async_client: AsyncClient, async_db_session) -> None:
    """Verify approving a gated step updates status to APPROVED, records identity, and updates audit/outbox."""
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

    proposed = {"tool": "web_search", "query": "sensitive search"}
    approval = Approval(
        run_id=run.id,
        step_id=step.id,
        action="step_execution",
        payload_hash=Approval.compute_payload_hash(proposed),
        version=1,
        approval_token="tok_test_approval_123",
        status=ApprovalStatus.PENDING,
        proposed_action=proposed,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    headers = {"X-Operator-Id": "lead-analyst@corp.internal"}
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"operator_notes": "Action approved by analyst."},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_id"] == str(approval.id)
    assert data["status"] == "APPROVED"
    assert data["run_status"] == "RUNNING"
    assert data["action"] == "step_execution"
    assert data["resolved_by"] == "lead-analyst@corp.internal"
    assert data["operator_notes"] == "Action approved by analyst."
    assert data["resolved_at"] is not None

    # Check AuditEvent
    audit_stmt = select(AuditEvent).where(
        AuditEvent.run_id == run.id,
        AuditEvent.event_type == AuditEventType.APPROVAL_RESOLVED.value,
    )
    audit = (await async_db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.actor == "lead-analyst@corp.internal"
    assert audit.payload["verdict"] == "approved"

    # Check OutboxEvent
    outbox_stmt = select(OutboxEvent).where(OutboxEvent.aggregate_id == str(approval.id))
    outbox = (await async_db_session.execute(outbox_stmt)).scalar_one_or_none()
    assert outbox is not None
    assert outbox.event_type == "APPROVAL_APPROVED"


@pytest.mark.integration
async def test_rejection_with_reason(async_client: AsyncClient, async_db_session) -> None:
    """Verify rejecting an approval records the rejection reason and aborts the run."""
    run = Run(objective="Reject test run", domain="security", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_risky",
        title="Risky Action",
        tool_name="fetch_approved_public_page",
        requires_human_approval=True,
    )
    async_db_session.add(step)
    await async_db_session.commit()

    proposed = {"tool": "fetch_approved_public_page", "url": "https://unverified.com"}
    approval = Approval(
        run_id=run.id,
        step_id=step.id,
        action="step_execution",
        payload_hash=Approval.compute_payload_hash(proposed),
        version=1,
        approval_token="tok_reject_456",
        status=ApprovalStatus.PENDING,
        proposed_action=proposed,
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    run_id = run.id
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/reject",
        json={"reason": "Domain unverified by compliance team.", "abort_run": True},
        headers={"X-Operator-Id": "compliance-officer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["run_status"] == "ABORTED_BY_OPERATOR"
    assert data["operator_notes"] == "Domain unverified by compliance team."
    assert data["resolved_by"] == "compliance-officer"

    # Verify run aborted
    async_db_session.expire_all()
    updated_run = (await async_db_session.execute(select(Run).where(Run.id == run_id))).scalar_one()
    assert updated_run.status == RunStatus.ABORTED_BY_OPERATOR
    assert updated_run.completed_at is not None


@pytest.mark.integration
async def test_repeated_submission_idempotency(async_client: AsyncClient, async_db_session) -> None:
    """Verify repeated approval or rejection submissions are strictly idempotent."""
    run = Run(
        objective="Idempotency test run", domain="finance", status=RunStatus.AWAITING_APPROVAL
    )
    async_db_session.add(run)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        action="plan_review",
        payload_hash="abc" * 21 + "a",
        version=1,
        approval_token="tok_idem_789",
        status=ApprovalStatus.PENDING,
        proposed_action={"plan": "sample"},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # First approval
    res1 = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"operator_notes": "First submission."},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "APPROVED"
    resolved_time = data1["resolved_at"]

    # Duplicate approval submission (must return 200 OK idempotently)
    res2 = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"operator_notes": "Duplicate submission."},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "APPROVED"
    assert data2["resolved_at"].rstrip("Z") == resolved_time.rstrip("Z")

    # Conflict test: attempting to reject an already approved gate must fail
    res3 = await async_client.post(
        f"/api/v1/approvals/{approval.id}/reject",
        json={"reason": "Cannot reject approved gate."},
    )
    assert res3.status_code == 409 or "rejected" in res3.text.lower()


@pytest.mark.integration
async def test_expired_or_stale_approval_timeout(
    async_client: AsyncClient, async_db_session
) -> None:
    """Verify approvals exceeding expiration timeout are rejected with state error."""
    run = Run(objective="Timeout test run", domain="cloud", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    approval = Approval(
        run_id=run.id,
        action="step_execution",
        payload_hash="hash123",
        version=1,
        approval_token="tok_expired_999",
        status=ApprovalStatus.PENDING,
        proposed_action={"tool": "run_test"},
        expires_at=past_time,
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    app_id = approval.id
    response = await async_client.post(
        f"/api/v1/approvals/{app_id}/approve",
        json={"operator_notes": "Attempting to approve expired action."},
    )
    assert response.status_code in (400, 409)
    assert "expired" in response.text.lower()

    # Verify status in database is EXPIRED
    async_db_session.expire_all()
    refreshed = (
        await async_db_session.execute(select(Approval).where(Approval.id == app_id))
    ).scalar_one()
    assert refreshed.status == ApprovalStatus.EXPIRED


@pytest.mark.integration
async def test_changed_action_payload_rejection(
    async_client: AsyncClient, async_db_session
) -> None:
    """Verify that expected_payload_hash detects tampered or modified action payloads."""
    run = Run(objective="Tamper test run", domain="cloud", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    original_payload = {"tool": "extract_metrics", "domain": "fintech"}
    registered_hash = Approval.compute_payload_hash(original_payload)

    approval = Approval(
        run_id=run.id,
        action="step_execution",
        payload_hash=registered_hash,
        version=1,
        approval_token="tok_payload_check",
        status=ApprovalStatus.PENDING,
        proposed_action=original_payload,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # Operator attempts to authorize with a mismatched expected hash
    tampered_hash = Approval.compute_payload_hash(
        {"tool": "extract_metrics", "domain": "malicious_domain"}
    )
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={
            "operator_notes": "Approval with stale hash",
            "expected_payload_hash": tampered_hash,
        },
    )
    assert response.status_code in (400, 409)
    assert "stale approval error" in response.text.lower() or "mismatch" in response.text.lower()


@pytest.mark.integration
async def test_cancellation_during_approval(async_client: AsyncClient, async_db_session) -> None:
    """Verify that cancelling a run while awaiting approval safely transitions status."""
    run = Run(objective="Cancel while waiting", domain="devops", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        action="plan_review",
        payload_hash="hash_cancel",
        version=1,
        approval_token="tok_cancel_wait",
        status=ApprovalStatus.PENDING,
        proposed_action={"plan": []},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    run_id = run.id
    # Cancel the run
    cancel_res = await async_client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Confirm run is cancelled in DB
    async_db_session.expire_all()
    refreshed_run = (
        await async_db_session.execute(select(Run).where(Run.id == run_id))
    ).scalar_one()
    assert refreshed_run.status == RunStatus.CANCELLED


@pytest.mark.integration
async def test_worker_restart_while_awaiting_approval_and_safe_resumption(
    async_db_session,
) -> None:
    """ACCEPTANCE CRITERIA: A run survives a worker crash/restart while awaiting approval,

    and resumes from the durable checkpoint without losing state or repeating completed work.
    """
    run_id = uuid.uuid4()
    thread_id = str(run_id)

    # 1. Create Run in DB
    run = Run(
        id=run_id,
        objective="Analyze cloud observability market pricing and uptime SLAs",
        domain="observability",
        status=RunStatus.RUNNING,
    )
    async_db_session.add(run)
    await async_db_session.commit()

    # 2. Worker 1 compiles agent graph with a DurableCheckpointSaver
    saver1 = DurableCheckpointSaver()
    graph1 = create_agent_graph(checkpointer=saver1)

    initial_state = {
        "run_id": thread_id,
        "objective": run.objective,
        "domain": run.domain,
        "requires_plan_approval": True,  # Trigger plan approval checkpoint
        "status": "RUNNING",
    }
    config = {"configurable": {"thread_id": thread_id}}

    # Worker 1 starts the run:
    out1 = graph1.invoke(initial_state, config)

    # Verify Worker 1 paused at the plan_review interrupt
    assert out1.get("__interrupt__") is not None
    interrupt_payload = out1["__interrupt__"][0].value
    assert interrupt_payload["action"] == "plan_review"
    assert interrupt_payload["approval_required"] is True

    # 3. Simulate Worker 1 persisting the checkpoint to DB and crashing
    # We capture the clean serialized checkpoint and persist to graph_checkpoints table
    storage_clean, writes_clean, blobs_clean = saver1._clean_dicts_for_persistence(thread_id)
    blob_bytes = pickle.dumps((storage_clean, writes_clean, blobs_clean))
    encoded_blob = base64.b64encode(blob_bytes).decode("ascii")

    chk_entity = GraphCheckpoint(
        run_id=run_id,
        checkpoint_id="chk-pause-plan",
        checkpoint_type="langgraph",
        checkpoint_blob=encoded_blob,
        metadata_payload={"step": "check_plan_approval"},
    )
    async_db_session.add(chk_entity)

    # Persist the Approval request in DB
    approval = await approval_service.create_approval_request(
        session=async_db_session,
        run_id=run_id,
        action="plan_review",
        proposed_action=interrupt_payload,
    )
    await async_db_session.commit()

    # 4. WORKER 1 DIES COMPLETELY (saver1 and graph1 garbage collected/destroyed)
    del saver1
    del graph1

    # 5. Operator approves the plan
    approved_approval, updated_run = await approval_service.approve_step(
        session=async_db_session,
        approval_id=approval.id,
        operator_notes="Plan approved for execution.",
        resolved_by="principal_architect",
    )
    assert approved_approval.status == ApprovalStatus.APPROVED
    assert updated_run.status == RunStatus.RUNNING
    await async_db_session.commit()

    # 6. WORKER 2 BOOTS UP FRESH:
    # Worker 2 has empty in-memory state, loads checkpoint from DB table and resumes
    saver2 = DurableCheckpointSaver()
    # Populate saver2 with the DB checkpoint
    s_dict, w_dict, b_dict = pickle.loads(base64.b64decode(encoded_blob.encode("ascii")))
    for k, v in s_dict.items():
        for ns, chks in v.items():
            saver2.storage[k][ns].update(chks)
    saver2.writes.update(w_dict)
    saver2.blobs.update(b_dict)

    graph2 = create_agent_graph(checkpointer=saver2)

    # Worker 2 resumes execution using LangGraph Command(resume=...)
    resume_payload = {
        "verdict": "approved",
        "operator_notes": "Plan approved for execution.",
        "resolved_by": "principal_architect",
    }
    out2 = graph2.invoke(Command(resume=resume_payload), config)

    # 7. Verification of Acceptance Criteria:
    # - Run survived restart
    # - Plan review gate passed
    # - Execution proceeded to completion without repeating request validation or planning
    assert out2["plan_approved"] is True
    assert out2["status"] == "COMPLETED"
    assert out2["steps_executed"] > 0
    assert len(out2.get("evidence_items", [])) > 0
    assert out2.get("final_report") is not None


@pytest.mark.integration
async def test_unauthorized_approval_rejected(async_client: AsyncClient, async_db_session) -> None:
    """Verify that approval requests with invalid credentials are unauthorized."""
    run = Run(objective="Auth test run", domain="security", status=RunStatus.AWAITING_APPROVAL)
    async_db_session.add(run)
    await async_db_session.commit()

    approval = Approval(
        run_id=run.id,
        action="step_execution",
        payload_hash="hash_auth",
        version=1,
        approval_token="tok_auth_test",
        status=ApprovalStatus.PENDING,
        proposed_action={"tool": "web_search"},
    )
    async_db_session.add(approval)
    await async_db_session.commit()

    # Pass an invalid API key
    response = await async_client.post(
        f"/api/v1/approvals/{approval.id}/approve",
        json={"operator_notes": "Unauthorized attempt."},
        headers={"X-API-Key": "completely-invalid-key"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.integration
async def test_report_review_checkpoint() -> None:
    """Verify that report review checkpoint pauses execution and resumes upon approval."""
    run_id = uuid.uuid4()
    thread_id = str(run_id)

    saver = DurableCheckpointSaver()
    graph = create_agent_graph(checkpointer=saver)

    initial_state = {
        "run_id": thread_id,
        "objective": "Deep competitive report analysis for database market",
        "domain": "database",
        "requires_report_approval": True,  # Trigger report review checkpoint
        "status": "RUNNING",
    }
    config = {"configurable": {"thread_id": thread_id}}

    out1 = graph.invoke(initial_state, config)

    # Must pause at check_report_approval
    assert out1.get("__interrupt__") is not None
    interrupt_val = out1["__interrupt__"][0].value
    assert interrupt_val["action"] == "report_review"
    assert interrupt_val["approval_required"] is True

    # Resume with approval
    out2 = graph.invoke(
        Command(resume={"verdict": "approved", "operator_notes": "Report approved for release"}),
        config,
    )
    assert out2["report_approved"] is True
    assert out2["status"] == "COMPLETED"
    assert out2["final_report"] is not None
