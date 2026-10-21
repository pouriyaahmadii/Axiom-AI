"""Celery worker tasks for durable, idempotent background run execution."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import (
    DeterministicValidationError,
    TransientWorkerError,
)
from app.core.security import generate_secure_token
from app.db.session import get_sync_session
from app.models.approval import Approval
from app.models.audit import AuditEvent
from app.models.enums import ApprovalStatus, AuditEventType, LLMCallStatus, RunStatus, StepStatus
from app.models.llm import LLMCall
from app.models.run import Run
from app.models.step import RunStep
from app.providers import get_llm_provider, sanitize_prompt_preview
from app.workers.celery_app import celery_app, is_worker_shutting_down

logger = structlog.get_logger(__name__)
settings = get_settings()

TERMINAL_RUN_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.COMPLETED_WITH_WARNINGS,
    RunStatus.CANCELLED,
    RunStatus.FAILED,
    RunStatus.ABORTED_BY_OPERATOR,
}


def create_default_mock_plan(run: Run) -> list[dict[str, Any]]:
    """Synthesize a bounded, default plan for the competitive analysis demo."""
    return [
        {
            "step_index": 1,
            "step_identifier": "search_landscape",
            "title": f"Search market landscape for {run.domain}",
            "tool_name": "web_search",
            "parameters": {"query": f"{run.domain} competitors {run.geography or ''}".strip()},
            "requires_human_approval": False,
        },
        {
            "step_index": 2,
            "step_identifier": "fetch_competitor_data",
            "title": "Retrieve competitor profiles and documentation",
            "tool_name": "fetch_document",
            "parameters": {"domain": run.domain},
            "requires_human_approval": False,
        },
        {
            "step_index": 3,
            "step_identifier": "synthesize_analysis",
            "title": "Synthesize competitor metrics and comparison matrix",
            "tool_name": "extract_metrics",
            "parameters": {"domain": run.domain},
            "requires_human_approval": False,
        },
    ]


@celery_app.task(
    bind=True,
    name="agentops.execute_run",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(TransientWorkerError,),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
)
def execute_run(self: Any, run_id: str, correlation_id: str | None = None) -> dict[str, Any]:
    """Durable worker task executing an end-to-end bounded research run.

    Guarantees:
    - At-least-once Celery delivery handled idempotently.
    - Terminal states (COMPLETED, CANCELLED, FAILED) are never overwritten by stale workers.
    - Cancellation checked at safe step boundaries.
    - Deterministic errors fail immediately; transient errors retry with backoff.
    - Timeouts handled cleanly via SoftTimeLimitExceeded.
    """
    logger.info("execute_run_started", run_id=run_id, attempt=self.request.retries + 1)
    run_uuid = uuid.UUID(run_id)

    with get_sync_session() as session:
        run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one_or_none()
        if not run:
            logger.error("execute_run_not_found", run_id=run_id)
            return {"status": "NOT_FOUND", "run_id": run_id}

        # 1. Check for cancellation at initial boundary
        if run.status == RunStatus.CANCELLED:
            logger.info("run_cancelled_prior_to_execution", run_id=run_id)
            return {"status": "CANCELLED_AT_BOUNDARY", "run_id": run_id}

        # 2. Guard against duplicate delivery on runs already in a terminal state
        if run.status in TERMINAL_RUN_STATUSES:
            logger.info(
                "duplicate_delivery_ignored",
                run_id=run_id,
                current_status=run.status.value,
                message="Run is already in a terminal state; duplicate Celery message ignored.",
            )
            return {
                "status": "SKIPPED_DUPLICATE_DELIVERY",
                "run_id": run_id,
                "current_status": run.status.value,
            }

        # 3. Guard against duplicate delivery on paused approval gates
        if run.status == RunStatus.AWAITING_APPROVAL:
            logger.info(
                "run_awaiting_approval_ignored",
                run_id=run_id,
                message="Run is currently awaiting operator approval; skipping task invocation.",
            )
            return {
                "status": "SKIPPED_AWAITING_APPROVAL",
                "run_id": run_id,
            }

        # 4. Record execution attempt
        run.attempt_count += 1
        if run.status == RunStatus.QUEUED:
            run.status = RunStatus.PLANNING
            session.add(
                AuditEvent(
                    run_id=run.id,
                    correlation_id=correlation_id,
                    event_type=AuditEventType.STEP_STARTED.value,
                    actor="celery_worker",
                    payload={"phase": "planning", "attempt": run.attempt_count},
                )
            )
            session.commit()

    try:
        # 5. Planning Phase: populate plan and steps if not already created
        with get_sync_session() as session:
            run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one()

            # Guard: check if cancelled while acquiring planning session
            if run.status == RunStatus.CANCELLED:
                return {"status": "CANCELLED_AT_BOUNDARY", "run_id": run_id}

            existing_steps = (
                session.execute(
                    select(RunStep)
                    .where(RunStep.run_id == run_uuid)
                    .order_by(RunStep.step_index.asc())
                )
                .scalars()
                .all()
            )

            if not existing_steps:
                provider = get_llm_provider(run.llm_provider)
                plan_res = provider.generate_plan(
                    objective=run.objective,
                    domain=run.domain,
                    geography=run.geography,
                )
                plan_steps_data = [s.model_dump() for s in plan_res.data.steps]
                run.raw_plan = {"total_steps": len(plan_steps_data), "steps": plan_steps_data}
                run.estimated_cost_usd += plan_res.usage.cost_usd

                # Persist auditable LLMCall record
                llm_call = LLMCall(
                    run_id=run.id,
                    provider=plan_res.provider,
                    model_name=plan_res.model,
                    prompt_tokens=plan_res.usage.prompt_tokens,
                    completion_tokens=plan_res.usage.completion_tokens,
                    total_tokens=plan_res.usage.total_tokens,
                    cost_usd=plan_res.usage.cost_usd,
                    duration_ms=plan_res.usage.latency_ms,
                    status=LLMCallStatus.SUCCESS,
                    prompt_preview=sanitize_prompt_preview(run.objective),
                    completion_preview=sanitize_prompt_preview(plan_res.raw_content or ""),
                )
                session.add(llm_call)

                for step_def in plan_steps_data:
                    step_entity = RunStep(
                        run_id=run.id,
                        step_index=step_def["step_index"],
                        step_identifier=step_def["step_identifier"],
                        title=step_def["title"],
                        tool_name=step_def["tool_name"],
                        parameters=step_def["parameters"],
                        requires_human_approval=step_def["requires_human_approval"],
                        status=StepStatus.PENDING,
                        retry_count=0,
                    )
                    session.add(step_entity)

                session.add(
                    AuditEvent(
                        run_id=run.id,
                        correlation_id=correlation_id,
                        event_type=AuditEventType.PLAN_SYNTHESIZED.value,
                        actor="celery_worker",
                        payload={"total_steps": len(plan_steps_data), "provider": run.llm_provider},
                    )
                )

            run.status = RunStatus.RUNNING
            session.commit()

        # 6. Step Execution Loop: iterate sequentially with boundary checks and state commits
        with get_sync_session() as session:
            steps = (
                session.execute(
                    select(RunStep)
                    .where(RunStep.run_id == run_uuid)
                    .order_by(RunStep.step_index.asc())
                )
                .scalars()
                .all()
            )

            for step in steps:
                if step.status == StepStatus.COMPLETED or step.status == StepStatus.SKIPPED:
                    continue

                # Boundary Check A: Graceful worker shutdown check
                if is_worker_shutting_down():
                    logger.warning(
                        "worker_shutting_down_boundary", run_id=run_id, step_index=step.step_index
                    )
                    return {"status": "INTERRUPTED_SHUTDOWN", "run_id": run_id}

                # Boundary Check B: Operator cancellation check
                run_check = session.execute(
                    select(Run.status).where(Run.id == run_uuid)
                ).scalar_one()
                if run_check == RunStatus.CANCELLED:
                    logger.info(
                        "cancellation_detected_at_step_boundary",
                        run_id=run_id,
                        step_index=step.step_index,
                    )
                    step.status = StepStatus.SKIPPED
                    session.commit()
                    return {"status": "CANCELLED_AT_BOUNDARY", "run_id": run_id}

                # Boundary Check C: Human approval gate pause
                if step.requires_human_approval:
                    approval = session.execute(
                        select(Approval).where(Approval.step_id == step.id)
                    ).scalar_one_or_none()

                    current_payload = {
                        "tool": step.tool_name,
                        "parameters": step.parameters,
                    }

                    # Check for changed payload or expired approval
                    is_stale_or_expired = False
                    if approval:
                        if approval.is_expired():
                            approval.status = ApprovalStatus.EXPIRED
                            is_stale_or_expired = True
                        elif not approval.matches_payload(current_payload):
                            logger.warning(
                                "stale_approval_payload_mismatch",
                                run_id=run_id,
                                step_id=str(step.id),
                                registered_hash=approval.payload_hash,
                            )
                            is_stale_or_expired = True

                    if (
                        not approval
                        or approval.status != ApprovalStatus.APPROVED
                        or is_stale_or_expired
                    ):
                        run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one()
                        run.status = RunStatus.AWAITING_APPROVAL

                        if not approval or is_stale_or_expired:
                            new_approval = Approval(
                                run_id=run.id,
                                step_id=step.id,
                                action="step_execution",
                                payload_hash=Approval.compute_payload_hash(current_payload),
                                version=1 if not approval else approval.version + 1,
                                approval_token=generate_secure_token(),
                                status=ApprovalStatus.PENDING,
                                proposed_action=current_payload,
                                expires_at=datetime.now(timezone.utc)
                                + timedelta(seconds=settings.APPROVAL_TIMEOUT_SECONDS),
                            )
                            session.add(new_approval)

                        session.add(
                            AuditEvent(
                                run_id=run.id,
                                step_id=step.id,
                                correlation_id=correlation_id,
                                event_type=AuditEventType.APPROVAL_REQUESTED.value,
                                actor="celery_worker",
                                payload={
                                    "step_identifier": step.step_identifier,
                                    "action": "step_execution",
                                    "payload_hash": Approval.compute_payload_hash(current_payload),
                                },
                            )
                        )
                        session.commit()
                        logger.info(
                            "run_paused_for_approval", run_id=run_id, step_index=step.step_index
                        )
                        return {
                            "status": "PAUSED_FOR_APPROVAL",
                            "run_id": run_id,
                            "step_id": str(step.id),
                        }

                # Persist State BEFORE step execution
                step.status = StepStatus.RUNNING
                step.started_at = datetime.now(timezone.utc)
                session.add(
                    AuditEvent(
                        run_id=run_uuid,
                        step_id=step.id,
                        correlation_id=correlation_id,
                        event_type=AuditEventType.STEP_STARTED.value,
                        actor="celery_worker",
                        payload={"step_index": step.step_index, "tool_name": step.tool_name},
                    )
                )
                session.commit()

                # Execute step work with error classification
                try:
                    # Deterministic validation check: simulate parameter validation
                    if step.parameters.get("__test_fail_deterministic__"):
                        raise DeterministicValidationError(
                            "Simulated deterministic validation failure."
                        )

                    # Transient failure check: simulate network error
                    if step.parameters.get("__test_fail_transient__"):
                        raise TransientWorkerError("Simulated transient connection reset.")

                    # Persist State AFTER successful step execution
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.now(timezone.utc)
                    session.add(
                        AuditEvent(
                            run_id=run_uuid,
                            step_id=step.id,
                            correlation_id=correlation_id,
                            event_type=AuditEventType.STEP_COMPLETED.value,
                            actor="celery_worker",
                            payload={"step_index": step.step_index, "status": "COMPLETED"},
                        )
                    )
                    session.commit()

                except DeterministicValidationError as err:
                    # Deterministic errors fail immediately; do NOT retry
                    step.status = StepStatus.FAILED
                    step.error_message = str(err)
                    step.completed_at = datetime.now(timezone.utc)

                    run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one()
                    run.status = RunStatus.FAILED
                    run.error_message = (
                        f"Step '{step.step_identifier}' failed with deterministic error: {err}"
                    )
                    run.completed_at = datetime.now(timezone.utc)

                    session.add(
                        AuditEvent(
                            run_id=run_uuid,
                            step_id=step.id,
                            correlation_id=correlation_id,
                            event_type=AuditEventType.STEP_FAILED.value,
                            actor="celery_worker",
                            payload={"error": str(err), "deterministic": True},
                        )
                    )
                    session.commit()
                    logger.error("step_failed_deterministic", run_id=run_id, error=str(err))
                    return {"status": "FAILED_DETERMINISTIC_ERROR", "error": str(err)}

                except TransientWorkerError as err:
                    # Transient error: handle step-level retries or raise to Celery
                    step.retry_count += 1
                    step.error_message = str(err)
                    session.add(
                        AuditEvent(
                            run_id=run_uuid,
                            step_id=step.id,
                            correlation_id=correlation_id,
                            event_type=AuditEventType.STEP_RETRYING.value,
                            actor="celery_worker",
                            payload={"retry_count": step.retry_count, "error": str(err)},
                        )
                    )
                    session.commit()
                    logger.warning(
                        "step_transient_retry",
                        run_id=run_id,
                        step_index=step.step_index,
                        retry=step.retry_count,
                    )
                    raise

        # 7. Finalization: Guard against stale worker overwriting terminal state
        with get_sync_session() as session:
            run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one()

            # Prevent stale worker overwriting operator cancellation or failure
            if run.status in TERMINAL_RUN_STATUSES:
                logger.warning(
                    "stale_worker_terminal_state_protected",
                    run_id=run_id,
                    current_status=run.status.value,
                )
                return {
                    "status": "SKIPPED_TERMINAL_PROTECTED",
                    "run_id": run_id,
                    "current_status": run.status.value,
                }

            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            session.add(
                AuditEvent(
                    run_id=run.id,
                    correlation_id=correlation_id,
                    event_type=AuditEventType.RUN_COMPLETED.value,
                    actor="celery_worker",
                    payload={"completed_at": run.completed_at.isoformat()},
                )
            )
            session.commit()
            logger.info("execute_run_completed", run_id=run_id)
            return {"status": "COMPLETED", "run_id": run_id}

    except SoftTimeLimitExceeded:
        # Handle execution timeout cleanly
        logger.error("execute_run_soft_time_limit_exceeded", run_id=run_id)
        with get_sync_session() as session:
            run = session.execute(select(Run).where(Run.id == run_uuid)).scalar_one_or_none()
            if run and run.status not in TERMINAL_RUN_STATUSES:
                run.status = RunStatus.FAILED
                run.error_message = f"Execution exceeded maximum allowed time limit ({settings.MAX_EXECUTION_SECONDS}s)."
                run.completed_at = datetime.now(timezone.utc)

                # Mark any active step as FAILED
                running_steps = (
                    session.execute(
                        select(RunStep).where(
                            RunStep.run_id == run_uuid, RunStep.status == StepStatus.RUNNING
                        )
                    )
                    .scalars()
                    .all()
                )
                for step in running_steps:
                    step.status = StepStatus.FAILED
                    step.error_message = "Step timed out due to global execution limit."
                    step.completed_at = datetime.now(timezone.utc)

                session.add(
                    AuditEvent(
                        run_id=run_uuid,
                        correlation_id=correlation_id,
                        event_type=AuditEventType.RUN_FAILED.value,
                        actor="celery_worker",
                        payload={
                            "reason": "timeout",
                            "limit_seconds": settings.MAX_EXECUTION_SECONDS,
                        },
                    )
                )
                session.commit()

        return {"status": "FAILED_TIMEOUT", "run_id": run_id}
