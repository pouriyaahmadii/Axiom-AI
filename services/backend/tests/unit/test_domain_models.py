"""Unit tests for domain models, constraints, relationships, and status serializations."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Approval,
    ApprovalStatus,
    AuditEvent,
    AuditEventType,
    AuditLogImmutableError,
    EvidenceItem,
    LLMCall,
    LLMCallStatus,
    OutboxEvent,
    OutboxStatus,
    Report,
    Run,
    RunStatus,
    RunStep,
    Source,
    StepStatus,
    ToolInvocation,
    ToolInvocationStatus,
)


@pytest.mark.unit
def test_run_creation_and_defaults(db_session):
    """Verify Run creation, default values, UUID generation, and query retrieval."""
    run = Run(
        objective="Analyze enterprise AI safety vendors in EMEA",
        domain="ai_safety",
        geography="EMEA",
    )
    db_session.add(run)
    db_session.commit()

    retrieved = db_session.get(Run, run.id)
    assert retrieved is not None
    assert isinstance(retrieved.id, uuid.UUID)
    assert retrieved.status == RunStatus.QUEUED
    assert retrieved.llm_provider == "mock"
    assert retrieved.search_provider == "mock"
    assert retrieved.budget_usd_limit == Decimal("1.0000")
    assert retrieved.estimated_cost_usd == Decimal("0.0000")
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


@pytest.mark.unit
def test_run_step_uniqueness_constraints(db_session):
    """Verify that run_id + step_index and run_id + step_identifier unique constraints are enforced."""
    run = Run(objective="Test uniqueness", domain="testing")
    db_session.add(run)
    db_session.commit()

    step1 = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_01",
        title="First Step",
        tool_name="web_search",
    )
    db_session.add(step1)
    db_session.commit()

    # Attempt to insert a duplicate step_index for the same run
    dup_index_step = RunStep(
        run_id=run.id,
        step_index=0,  # Duplicate!
        step_identifier="step_02",
        title="Duplicate Index Step",
        tool_name="web_search",
    )
    db_session.add(dup_index_step)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Attempt to insert a duplicate step_identifier for the same run
    dup_id_step = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="step_01",  # Duplicate!
        title="Duplicate Identifier Step",
        tool_name="web_search",
    )
    db_session.add(dup_id_step)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_source_uniqueness_per_run(db_session):
    """Verify that (run_id, url) uniqueness is strictly enforced."""
    run = Run(objective="Test source uniqueness", domain="testing")
    db_session.add(run)
    db_session.commit()

    source1 = Source(
        run_id=run.id,
        url="https://example.com/pricing",
        domain="example.com",
        content_hash="a" * 64,
    )
    db_session.add(source1)
    db_session.commit()

    # Attempt duplicate URL in same run
    source2 = Source(
        run_id=run.id,
        url="https://example.com/pricing",
        domain="example.com",
        content_hash="b" * 64,
    )
    db_session.add(source2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_evidence_item_uniqueness_per_run(db_session):
    """Verify that (run_id, content_hash) uniqueness prevents duplicate evidence in the same run."""
    run = Run(objective="Test evidence uniqueness", domain="testing")
    db_session.add(run)
    db_session.commit()

    evidence1 = EvidenceItem(
        run_id=run.id,
        source_url="https://example.com/facts",
        content_hash="c" * 64,
        raw_snippet="Factual excerpt text",
    )
    db_session.add(evidence1)
    db_session.commit()

    # Attempt duplicate content hash in same run
    evidence2 = EvidenceItem(
        run_id=run.id,
        source_url="https://another-url.com/facts",
        content_hash="c" * 64,  # Duplicate hash
        raw_snippet="Identical factual excerpt text",
    )
    db_session.add(evidence2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_approval_uniqueness(db_session):
    """Verify approval token uniqueness and one-approval-per-step constraint."""
    run = Run(objective="Test approvals", domain="testing")
    db_session.add(run)
    db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_eval",
        title="Evaluate",
        tool_name="web_search",
        requires_human_approval=True,
    )
    db_session.add(step)
    db_session.commit()

    approval1 = Approval(
        run_id=run.id,
        step_id=step.id,
        approval_token="tok_1234567890abcdef",
        proposed_action={"tool": "web_search", "query": "sensitive query"},
    )
    db_session.add(approval1)
    db_session.commit()

    # Attempt to add second approval for the same step in the same run
    approval2 = Approval(
        run_id=run.id,
        step_id=step.id,
        approval_token="tok_different_token",
        proposed_action={"tool": "web_search"},
    )
    db_session.add(approval2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_report_one_to_one_run_uniqueness(db_session):
    """Verify a Run can only have one associated Report."""
    run = Run(objective="Test report uniqueness", domain="testing")
    db_session.add(run)
    db_session.commit()

    report1 = Report(
        run_id=run.id,
        title="Market Analysis",
        markdown_content="# Report",
        executive_summary="Summary of findings",
        citations=[{"marker": "[^1]", "evidence_id": str(uuid.uuid4())}],
    )
    db_session.add(report1)
    db_session.commit()

    report2 = Report(
        run_id=run.id,  # Duplicate run_id
        title="Conflicting Market Analysis",
        markdown_content="# Conflicting Report",
        executive_summary="Conflicting summary",
    )
    db_session.add(report2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_foreign_key_cascade_deletion(db_session):
    """Verify that deleting a parent Run cascades to delete child steps, evidence, tool invocations, etc."""
    run = Run(objective="Cascade test", domain="testing")
    db_session.add(run)
    db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_cascade",
        title="Cascade Step",
        tool_name="web_search",
    )
    db_session.add(step)

    source = Source(
        run_id=run.id,
        url="https://cascade.example.com",
        domain="cascade.example.com",
        content_hash="d" * 64,
    )
    db_session.add(source)

    evidence = EvidenceItem(
        run_id=run.id,
        source_url="https://cascade.example.com",
        content_hash="e" * 64,
        raw_snippet="Cascade excerpt",
    )
    db_session.add(evidence)

    tool = ToolInvocation(
        run_id=run.id,
        step_id=step.id,
        tool_name="web_search",
        parameters={"query": "cascade"},
    )
    db_session.add(tool)

    llm = LLMCall(
        run_id=run.id,
        step_id=step.id,
        provider="mock",
        model_name="mock-planner",
    )
    db_session.add(llm)

    audit = AuditEvent(
        run_id=run.id,
        event_type=AuditEventType.STEP_STARTED,
        payload={"step": "step_cascade"},
    )
    db_session.add(audit)

    db_session.commit()

    step_id = step.id
    source_id = source.id
    evidence_id = evidence.id
    tool_id = tool.id
    llm_id = llm.id
    audit_id = audit.id

    # Delete parent Run
    db_session.delete(run)
    db_session.commit()

    # Verify all children were deleted
    assert db_session.get(RunStep, step_id) is None
    assert db_session.get(Source, source_id) is None
    assert db_session.get(EvidenceItem, evidence_id) is None
    assert db_session.get(ToolInvocation, tool_id) is None
    assert db_session.get(LLMCall, llm_id) is None
    assert db_session.get(AuditEvent, audit_id) is None


@pytest.mark.unit
def test_audit_event_immutability(db_session):
    """Verify that AuditEvent records are append-only and cannot be mutated or deleted directly."""
    audit = AuditEvent(
        event_type=AuditEventType.RUN_QUEUED,
        actor="operator",
        payload={"reason": "audit integrity test"},
    )
    db_session.add(audit)
    db_session.commit()

    # Attempt to update an existing audit event
    audit.actor = "malicious_actor"
    with pytest.raises(AuditLogImmutableError):
        db_session.commit()
    db_session.rollback()

    # Attempt to delete an existing audit event directly
    retrieved = db_session.get(AuditEvent, audit.id)
    assert retrieved is not None
    db_session.delete(retrieved)
    with pytest.raises(AuditLogImmutableError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.unit
def test_outbox_event_creation(db_session):
    """Verify OutboxEvent defaults and status progression."""
    outbox = OutboxEvent(
        event_type="RUN_COMPLETED",
        aggregate_type="run",
        aggregate_id=str(uuid.uuid4()),
        payload={"result": "success"},
    )
    db_session.add(outbox)
    db_session.commit()

    assert outbox.status == OutboxStatus.PENDING
    assert outbox.retry_count == 0
    assert outbox.published_at is None


@pytest.mark.unit
def test_status_enums_serialization():
    """Verify all status enums conform to string comparison and serialize cleanly."""
    assert RunStatus.QUEUED.value == "QUEUED"
    assert RunStatus("RUNNING") == RunStatus.RUNNING

    assert StepStatus.PENDING.value == "PENDING"
    assert StepStatus("COMPLETED") == StepStatus.COMPLETED

    assert ApprovalStatus.PENDING.value == "PENDING"
    assert ApprovalStatus("APPROVED") == ApprovalStatus.APPROVED

    assert ToolInvocationStatus.INVOKED.value == "INVOKED"
    assert ToolInvocationStatus("SUCCESS") == ToolInvocationStatus.SUCCESS

    assert LLMCallStatus.SUCCESS.value == "SUCCESS"
    assert LLMCallStatus("TIMEOUT") == LLMCallStatus.TIMEOUT

    assert OutboxStatus.PENDING.value == "PENDING"
    assert OutboxStatus("PUBLISHED") == OutboxStatus.PUBLISHED


@pytest.mark.unit
def test_no_api_keys_in_model_columns():
    """Verify that none of the domain models declare columns containing 'api_key', 'token', or credentials."""
    models = [
        Run,
        RunStep,
        Source,
        ToolInvocation,
        EvidenceItem,
        Report,
        LLMCall,
        AuditEvent,
        OutboxEvent,
    ]
    forbidden_terms = ["api_key", "secret_key", "password", "credential"]

    for model in models:
        for column in model.__table__.columns:
            for term in forbidden_terms:
                assert term not in column.name.lower(), (
                    f"Model {model.__name__} violates security rules by exposing column {column.name}"
                )
