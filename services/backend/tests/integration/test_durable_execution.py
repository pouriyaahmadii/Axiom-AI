"""Integration tests for durable asynchronous execution, outbox recovery, timeouts, and cancellation."""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from kombu.exceptions import OperationalError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import TransientWorkerError
from app.models.audit import AuditEvent
from app.models.enums import AuditEventType, OutboxStatus, RunStatus, StepStatus
from app.models.outbox import OutboxEvent
from app.models.run import Run
from app.models.step import RunStep
from app.services.outbox_service import dispatch_outbox_event_sync, dispatch_pending_outbox_sync
from app.services.recovery_service import reconcile_interrupted_runs
from app.workers.tasks import execute_run


@pytest.fixture
def sync_session_ctx(migrated_db_engine):
    """Context manager yielding test sync sessions for Celery tasks."""
    factory = sessionmaker(
        bind=migrated_db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    @contextmanager
    def _ctx():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _ctx


def _create_test_run(
    session: Session,
    status: RunStatus = RunStatus.QUEUED,
    objective: str = "Test durable execution objective",
    idempotency_key: str | None = None,
) -> Run:
    run = Run(
        id=uuid.uuid4(),
        objective=objective,
        domain="technology",
        status=status,
        llm_provider="mock",
        search_provider="mock",
        budget_usd_limit=Decimal("1.0000"),
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_key=idempotency_key,
        attempt_count=0,
    )
    session.add(run)
    session.commit()
    return run


def test_duplicate_celery_delivery_ignored(db_session, sync_session_ctx, monkeypatch):
    """Test requirement 3: Duplicate job delivery cannot create duplicate logical runs."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.QUEUED)
    run_id_str = str(run.id)

    # First delivery: executes to completion
    result_first = execute_run(run_id_str)
    assert result_first["status"] == "COMPLETED"

    # Verify run and steps
    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.COMPLETED
    assert reloaded_run.attempt_count == 1

    steps = db_session.execute(select(RunStep).where(RunStep.run_id == run.id)).scalars().all()
    initial_step_count = len(steps)
    assert initial_step_count == 3
    assert all(s.status == StepStatus.COMPLETED for s in steps)

    # Second delivery: simulate at-least-once Celery duplicate delivery
    result_second = execute_run(run_id_str)
    assert result_second["status"] == "SKIPPED_DUPLICATE_DELIVERY"

    # Verify no state corruption or duplicate steps created
    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.COMPLETED
    assert reloaded_run.attempt_count == 1  # Not incremented on duplicate

    reloaded_steps = (
        db_session.execute(select(RunStep).where(RunStep.run_id == run.id)).scalars().all()
    )
    assert len(reloaded_steps) == initial_step_count


def test_worker_process_termination_recovery(db_session):
    """Test requirement 11: Pending or interrupted work is discovered and reconciled after worker crash."""
    run = _create_test_run(db_session, status=RunStatus.RUNNING)

    # Create an active in-flight step
    step = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="active_interrupted_step",
        title="Active Step",
        tool_name="web_search",
        parameters={},
        status=StepStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(step)

    # Simulate that worker died 10 minutes ago (stale updated_at)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    run.updated_at = stale_time
    db_session.commit()

    # Reconcile with 300s threshold
    reconciled = reconcile_interrupted_runs(db_session, stale_threshold_seconds=300)
    assert reconciled == 1

    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.FAILED
    assert "interrupted" in reloaded_run.error_message.lower()

    reloaded_step = db_session.execute(select(RunStep).where(RunStep.id == step.id)).scalar_one()
    assert reloaded_step.status == StepStatus.FAILED

    # Verify audit event
    audit = db_session.execute(
        select(AuditEvent).where(
            AuditEvent.run_id == run.id,
            AuditEvent.event_type == AuditEventType.RUN_FAILED.value,
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.actor == "recovery_service"


def test_deterministic_error_fails_immediately_without_infinite_retry(
    db_session, sync_session_ctx, monkeypatch
):
    """Test requirement 6: Do not retry deterministic validation errors indefinitely."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.QUEUED)
    # Inject a deterministic validation error parameter into default plan
    step = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="deterministic_step",
        title="Deterministic step",
        tool_name="web_search",
        parameters={"__test_fail_deterministic__": True},
        status=StepStatus.PENDING,
        retry_count=0,
    )
    db_session.add(step)
    db_session.commit()

    result = execute_run(str(run.id))
    assert result["status"] == "FAILED_DETERMINISTIC_ERROR"

    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.FAILED
    assert "deterministic" in reloaded_run.error_message.lower()

    reloaded_step = db_session.execute(select(RunStep).where(RunStep.id == step.id)).scalar_one()
    assert reloaded_step.status == StepStatus.FAILED
    assert reloaded_step.retry_count == 0  # Zero retries attempted


def test_transient_error_records_retry_attempt(db_session, sync_session_ctx, monkeypatch):
    """Test requirement 5: Bounded retries record attempts and execution status."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.QUEUED)
    step = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="transient_step",
        title="Transient step",
        tool_name="web_search",
        parameters={"__test_fail_transient__": True},
        status=StepStatus.PENDING,
        retry_count=0,
    )
    db_session.add(step)
    db_session.commit()

    # The task should raise TransientWorkerError for Celery retry handling
    with pytest.raises(TransientWorkerError):
        execute_run(str(run.id))

    db_session.expire_all()
    reloaded_step = db_session.execute(select(RunStep).where(RunStep.id == step.id)).scalar_one()
    assert reloaded_step.retry_count == 1
    assert "transient" in reloaded_step.error_message.lower()


def test_timeout_handling_with_soft_time_limit(db_session, sync_session_ctx, monkeypatch):
    """Test requirement 7: Execution timeouts and clear terminal failure states."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.QUEUED)

    # Simulate SoftTimeLimitExceeded inside the step execution loop
    def _mock_plan(*_args, **_kwargs):
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr("app.workers.tasks.create_default_mock_plan", _mock_plan)

    result = execute_run(str(run.id))
    assert result["status"] == "FAILED_TIMEOUT"

    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.FAILED
    assert "time limit" in reloaded_run.error_message.lower()


def test_cancellation_at_safe_execution_boundary(db_session, sync_session_ctx, monkeypatch):
    """Test requirement 9: Cancellation at safe execution boundaries."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.CANCELLED)
    result = execute_run(str(run.id))

    assert result["status"] == "CANCELLED_AT_BOUNDARY"
    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.CANCELLED


def test_stale_worker_cannot_overwrite_cancelled_terminal_state(
    db_session, sync_session_ctx, monkeypatch
):
    """Test requirement 12: Prevent stale workers from overwriting newer terminal state."""
    monkeypatch.setattr("app.workers.tasks.get_sync_session", sync_session_ctx)

    run = _create_test_run(db_session, status=RunStatus.QUEUED)

    # Step 1 completes, then external API cancels the run before finalization
    step1 = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="step_1",
        title="Step 1",
        tool_name="web_search",
        parameters={},
        status=StepStatus.COMPLETED,
    )
    db_session.add(step1)
    db_session.commit()

    # Now simulate operator cancellation arriving while worker was in flight
    run.status = RunStatus.CANCELLED
    db_session.commit()

    result = execute_run(str(run.id))
    assert result["status"] == "CANCELLED_AT_BOUNDARY"

    db_session.expire_all()
    reloaded_run = db_session.execute(select(Run).where(Run.id == run.id)).scalar_one()
    assert reloaded_run.status == RunStatus.CANCELLED


def test_broker_outage_does_not_lose_committed_run(db_session):
    """Test requirement 2 & 13: Transactional outbox retains event during broker outage."""
    run = _create_test_run(db_session, status=RunStatus.QUEUED)

    event = OutboxEvent(
        event_type="RUN_QUEUED",
        aggregate_type="run",
        aggregate_id=str(run.id),
        payload={"run_id": str(run.id), "status": "QUEUED"},
        status=OutboxStatus.PENDING,
        retry_count=0,
    )
    db_session.add(event)
    db_session.commit()

    # Simulate broker outage by patching celery send_task to raise OperationalError
    with patch(
        "app.services.outbox_service.celery_app.send_task",
        side_effect=OperationalError("Broker unreachable"),
    ):
        success = dispatch_outbox_event_sync(db_session, event)
        assert success is False

    db_session.expire_all()
    reloaded_event = db_session.execute(
        select(OutboxEvent).where(OutboxEvent.id == event.id)
    ).scalar_one()
    assert reloaded_event.status == OutboxStatus.PENDING
    assert reloaded_event.retry_count == 1
    assert "OperationalError" in reloaded_event.last_error


def test_outbox_publication_recovery(db_session):
    """Test requirement 2: Outbox publication recovery when broker is available."""
    run = _create_test_run(db_session, status=RunStatus.QUEUED)

    event = OutboxEvent(
        event_type="RUN_QUEUED",
        aggregate_type="run",
        aggregate_id=str(run.id),
        payload={"run_id": str(run.id), "status": "QUEUED"},
        status=OutboxStatus.PENDING,
        retry_count=0,
    )
    db_session.add(event)
    db_session.commit()

    # When broker succeeds
    with patch("app.services.outbox_service.celery_app.send_task", return_value=MagicMock()):
        published, failed = dispatch_pending_outbox_sync(db_session)
        assert published == 1
        assert failed == 0

    db_session.expire_all()
    reloaded_event = db_session.execute(
        select(OutboxEvent).where(OutboxEvent.id == event.id)
    ).scalar_one()
    assert reloaded_event.status == OutboxStatus.PUBLISHED
    assert reloaded_event.published_at is not None
    assert reloaded_event.last_error is None


@pytest.mark.asyncio
async def test_repeated_api_requests_with_same_idempotency_key(async_client, async_db_session):
    """Test requirement: Repeated API requests with the same idempotency key return existing run."""
    payload = {
        "objective": "Analyze competitor landscape for software tools in North America",
        "domain": "software",
        "geography": "North America",
        "idempotency_key": "idemp-key-durable-test-001",
    }

    # First request: accepts and returns 202
    resp1 = await async_client.post("/api/v1/runs", json=payload)
    assert resp1.status_code == 202
    run_id_1 = resp1.json()["run_id"]

    # Second request: identical payload and idempotency key
    resp2 = await async_client.post("/api/v1/runs", json=payload)
    assert resp2.status_code == 202
    run_id_2 = resp2.json()["run_id"]

    # Must be the exact same run
    assert run_id_1 == run_id_2

    # Verify database has exactly 1 run and 1 outbox event
    stmt_runs = select(Run).where(Run.idempotency_key == payload["idempotency_key"])
    result_runs = await async_db_session.execute(stmt_runs)
    all_runs = result_runs.scalars().all()
    assert len(all_runs) == 1

    stmt_outbox = select(OutboxEvent).where(OutboxEvent.aggregate_id == run_id_1)
    result_outbox = await async_db_session.execute(stmt_outbox)
    all_outbox = result_outbox.scalars().all()
    assert len(all_outbox) == 1
