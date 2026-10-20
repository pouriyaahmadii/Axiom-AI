"""Transactional Outbox service for reliable, atomic message publishing to Celery."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.enums import OutboxStatus
from app.models.outbox import OutboxEvent
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def dispatch_outbox_event_sync(session: Session, event: OutboxEvent) -> bool:
    """Publish a single outbox event to Celery using a synchronous database session.

    Returns:
        bool: True if publication succeeded, False if publication failed.
    """
    try:
        if event.event_type == "RUN_QUEUED":
            run_id = event.aggregate_id
            correlation_id = event.payload.get("correlation_id")
            celery_app.send_task(
                "agentops.execute_run",
                kwargs={"run_id": run_id, "correlation_id": correlation_id},
                queue="agentops.runs",
                task_id=f"run-{run_id}",
            )

        event.status = OutboxStatus.PUBLISHED
        event.published_at = datetime.now(timezone.utc)
        event.last_error = None
        session.flush()

        logger.info(
            "outbox_event_published",
            event_id=str(event.id),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
        )
        return True

    except Exception as exc:
        event.retry_count += 1
        event.last_error = f"{type(exc).__name__}: {exc}"
        event.status = OutboxStatus.PENDING
        session.flush()

        logger.warning(
            "outbox_event_publish_failed",
            event_id=str(event.id),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            retry_count=event.retry_count,
            error=str(exc),
        )
        return False


def dispatch_pending_outbox_sync(session: Session, limit: int = 50) -> tuple[int, int]:
    """Sweep and publish pending outbox events synchronously.

    Returns:
        tuple[int, int]: (published_count, failed_count)
    """
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxStatus.PENDING)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
    )
    events = session.execute(stmt).scalars().all()

    published = 0
    failed = 0
    for event in events:
        if dispatch_outbox_event_sync(session, event):
            published += 1
        else:
            failed += 1

    return published, failed


async def dispatch_outbox_event_async(session: AsyncSession, event: OutboxEvent) -> bool:
    """Publish a single outbox event to Celery using an asynchronous database session.

    Returns:
        bool: True if publication succeeded, False if publication failed.
    """
    try:
        if event.event_type == "RUN_QUEUED":
            run_id = event.aggregate_id
            correlation_id = event.payload.get("correlation_id")
            celery_app.send_task(
                "agentops.execute_run",
                kwargs={"run_id": run_id, "correlation_id": correlation_id},
                queue="agentops.runs",
                task_id=f"run-{run_id}",
            )

        event.status = OutboxStatus.PUBLISHED
        event.published_at = datetime.now(timezone.utc)
        event.last_error = None
        await session.flush()

        logger.info(
            "outbox_event_published_async",
            event_id=str(event.id),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
        )
        return True

    except Exception as exc:
        event.retry_count += 1
        event.last_error = f"{type(exc).__name__}: {exc}"
        event.status = OutboxStatus.PENDING
        await session.flush()

        logger.warning(
            "outbox_event_publish_failed_async",
            event_id=str(event.id),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            retry_count=event.retry_count,
            error=str(exc),
        )
        return False


async def dispatch_pending_outbox_async(session: AsyncSession, limit: int = 50) -> tuple[int, int]:
    """Sweep and publish pending outbox events asynchronously.

    Returns:
        tuple[int, int]: (published_count, failed_count)
    """
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxStatus.PENDING)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    published = 0
    failed = 0
    for event in events:
        if await dispatch_outbox_event_async(session, event):
            published += 1
        else:
            failed += 1

    return published, failed
