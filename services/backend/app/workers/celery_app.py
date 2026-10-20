"""Celery application configuration and lifecycle signal handlers.

Configured with durable execution semantics: late acknowledgments, worker-lost
rejection, bounded timeouts, single-task prefetch, and graceful shutdown.
"""

from __future__ import annotations

import structlog
from celery import Celery
from celery.signals import worker_process_shutdown, worker_ready, worker_shutting_down

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

celery_app = Celery("agentops_worker")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Durable delivery configuration:
    # Acknowledge task only AFTER execution finishes (at-least-once guarantee).
    task_acks_late=True,
    # If worker process dies abruptly (SIGKILL/OOM), reject task to allow requeue.
    task_reject_on_worker_lost=True,
    # Prevent eager task hoarding; each worker thread takes 1 task at a time.
    worker_prefetch_multiplier=1,
    # Timeouts: soft limit raises SoftTimeLimitExceeded; hard limit terminates process.
    task_soft_time_limit=settings.MAX_EXECUTION_SECONDS,
    task_time_limit=settings.MAX_EXECUTION_SECONDS + 30,
    task_track_started=True,
    task_default_queue="agentops.runs",
)

# Global shutdown state flag for workers
_is_shutting_down = False


def is_worker_shutting_down() -> bool:
    """Return True if worker has received SIGTERM/SIGINT and is shutting down."""
    return _is_shutting_down


@worker_ready.connect
def handle_worker_ready(_sender: object, **_kwargs: object) -> None:
    """Log worker readiness on startup."""
    logger.info(
        "celery_worker_ready",
        broker_url=settings.CELERY_BROKER_URL,
        queues=["agentops.runs"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )


@worker_shutting_down.connect
def handle_worker_shutting_down(
    sig: object, how: object, exitcode: object, **_kwargs: object
) -> None:
    """Mark worker as shutting down to prevent starting new step batches."""
    global _is_shutting_down
    _is_shutting_down = True
    logger.info(
        "celery_worker_shutting_down",
        signal=sig,
        how=how,
        exitcode=exitcode,
        message="Worker received shutdown signal. Completing active transactions gracefully.",
    )


@worker_process_shutdown.connect
def handle_worker_process_shutdown(sender: object, **_kwargs: object) -> None:
    """Clean up resources upon process termination."""
    logger.info("celery_worker_process_shutdown", sender=str(sender))
