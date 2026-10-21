"""Correlation context propagation across API, worker, LangGraph, and tool layers."""

from __future__ import annotations

import contextvars
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any

import structlog

# ContextVars maintaining active correlation identifiers
_CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_correlation_id", default=None
)
_RUN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_run_id", default=None
)
_STEP_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_step_id", default=None
)
_STEP_INDEX: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "agentops_step_index", default=None
)
_CELERY_TASK_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_celery_task_id", default=None
)
_NODE_NAME: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_node_name", default=None
)
_TOOL_NAME: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agentops_tool_name", default=None
)


def get_correlation_id() -> str | None:
    """Retrieve active correlation ID."""
    return _CORRELATION_ID.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set active correlation ID and bind to structlog."""
    _CORRELATION_ID.set(correlation_id)
    if correlation_id:
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    else:
        structlog.contextvars.unbind_contextvars("correlation_id")


def get_run_id() -> str | None:
    """Retrieve active run ID."""
    return _RUN_ID.get()


def set_run_id(run_id: str | None) -> None:
    """Set active run ID and bind to structlog."""
    _RUN_ID.set(run_id)
    if run_id:
        structlog.contextvars.bind_contextvars(run_id=run_id)
    else:
        structlog.contextvars.unbind_contextvars("run_id")


def get_step_id() -> str | None:
    """Retrieve active step ID."""
    return _STEP_ID.get()


def get_step_index() -> int | None:
    """Retrieve active step index."""
    return _STEP_INDEX.get()


def set_step_context(step_id: str | None, step_index: int | None = None) -> None:
    """Set step context variables and bind to structlog."""
    _STEP_ID.set(step_id)
    _STEP_INDEX.set(step_index)
    binds: dict[str, Any] = {}
    if step_id:
        binds["step_id"] = step_id
    if step_index is not None:
        binds["step_index"] = step_index

    if binds:
        structlog.contextvars.bind_contextvars(**binds)
    else:
        structlog.contextvars.unbind_contextvars("step_id", "step_index")


def set_celery_task_context(task_id: str | None, task_name: str | None = None) -> None:
    """Set Celery task execution context."""
    _CELERY_TASK_ID.set(task_id)
    binds: dict[str, Any] = {}
    if task_id:
        binds["celery_task_id"] = task_id
    if task_name:
        binds["task_name"] = task_name

    if binds:
        structlog.contextvars.bind_contextvars(**binds)
    else:
        structlog.contextvars.unbind_contextvars("celery_task_id", "task_name")


def set_node_context(node_name: str | None) -> None:
    """Set active LangGraph execution node."""
    _NODE_NAME.set(node_name)
    if node_name:
        structlog.contextvars.bind_contextvars(node_name=node_name)
    else:
        structlog.contextvars.unbind_contextvars("node_name")


def set_tool_context(tool_name: str | None) -> None:
    """Set active tool name."""
    _TOOL_NAME.set(tool_name)
    if tool_name:
        structlog.contextvars.bind_contextvars(tool_name=tool_name)
    else:
        structlog.contextvars.unbind_contextvars("tool_name")


def get_active_correlation() -> dict[str, Any]:
    """Return dictionary of all currently active correlation parameters."""
    active: dict[str, Any] = {}
    if corr := _CORRELATION_ID.get():
        active["correlation_id"] = corr
    if run := _RUN_ID.get():
        active["run_id"] = run
    if step := _STEP_ID.get():
        active["step_id"] = step
    if (idx := _STEP_INDEX.get()) is not None:
        active["step_index"] = idx
    if task := _CELERY_TASK_ID.get():
        active["celery_task_id"] = task
    if node := _NODE_NAME.get():
        active["node_name"] = node
    if tool := _TOOL_NAME.get():
        active["tool_name"] = tool
    return active


def bind_correlation_context(**kwargs: Any) -> None:
    """Explicitly bind correlation attributes to context variables and structlog."""
    if "correlation_id" in kwargs:
        set_correlation_id(kwargs["correlation_id"])
    if "run_id" in kwargs:
        set_run_id(kwargs["run_id"])
    if "step_id" in kwargs or "step_index" in kwargs:
        set_step_context(kwargs.get("step_id"), kwargs.get("step_index"))
    if "celery_task_id" in kwargs:
        set_celery_task_context(kwargs["celery_task_id"])
    if "node_name" in kwargs:
        set_node_context(kwargs["node_name"])
    if "tool_name" in kwargs:
        set_tool_context(kwargs["tool_name"])


@contextmanager
def correlation_context(
    correlation_id: str | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    step_index: int | None = None,
    celery_task_id: str | None = None,
    node_name: str | None = None,
    tool_name: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Scoped context manager for temporary correlation parameter binding."""
    # Snapshot previous values
    prev_corr = _CORRELATION_ID.get()
    prev_run = _RUN_ID.get()
    prev_step = _STEP_ID.get()
    prev_index = _STEP_INDEX.get()
    prev_task = _CELERY_TASK_ID.get()
    prev_node = _NODE_NAME.get()
    prev_tool = _TOOL_NAME.get()

    # Apply new values if supplied
    if correlation_id is not None:
        set_correlation_id(correlation_id)
    if run_id is not None:
        set_run_id(run_id)
    if step_id is not None or step_index is not None:
        set_step_context(step_id, step_index)
    if celery_task_id is not None:
        set_celery_task_context(celery_task_id)
    if node_name is not None:
        set_node_context(node_name)
    if tool_name is not None:
        set_tool_context(tool_name)

    try:
        yield get_active_correlation()
    finally:
        # Restore prior state
        set_correlation_id(prev_corr)
        set_run_id(prev_run)
        set_step_context(prev_step, prev_index)
        set_celery_task_context(prev_task)
        set_node_context(prev_node)
        set_tool_context(prev_tool)


def extract_correlation_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Extract standard correlation headers from HTTP request headers or Celery metadata."""
    extracted: dict[str, str] = {}
    for key, val in headers.items():
        lower_k = key.lower()
        if lower_k in ("x-correlation-id", "x-request-id", "correlation_id", "request_id"):
            extracted["correlation_id"] = val
        elif lower_k in ("x-run-id", "run_id"):
            extracted["run_id"] = val
        elif lower_k == "traceparent":
            extracted["traceparent"] = val
        elif lower_k == "tracestate":
            extracted["tracestate"] = val
    return extracted


def inject_correlation_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject active correlation parameters into an outgoing HTTP or Celery header dictionary."""
    carrier = dict(headers or {})
    if corr := get_correlation_id():
        carrier["X-Correlation-ID"] = corr
    if run := get_run_id():
        carrier["X-Run-ID"] = run
    return carrier
