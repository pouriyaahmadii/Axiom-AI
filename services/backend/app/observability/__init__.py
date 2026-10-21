"""OpenTelemetry-compatible tracing, structured JSON logging, redaction, and metrics."""

from app.observability.context import (
    bind_correlation_context,
    correlation_context,
    extract_correlation_headers,
    get_active_correlation,
    get_correlation_id,
    get_run_id,
    get_step_id,
    get_step_index,
    inject_correlation_headers,
    set_celery_task_context,
    set_correlation_id,
    set_node_context,
    set_run_id,
    set_step_context,
    set_tool_context,
)
from app.observability.metrics import MetricsRegistry, get_metrics, metrics
from app.observability.redactor import (
    is_sensitive_key,
    redact_data,
    redact_log_event,
    sanitize_string,
)
from app.observability.tracer import (
    extract_traceparent,
    get_tracer,
    init_tracer,
    inject_traceparent,
    trace_span,
)

__all__ = [
    # Correlation & Context
    "set_correlation_id",
    "get_correlation_id",
    "set_run_id",
    "get_run_id",
    "set_step_context",
    "get_step_id",
    "get_step_index",
    "set_celery_task_context",
    "set_node_context",
    "set_tool_context",
    "get_active_correlation",
    "correlation_context",
    "bind_correlation_context",
    "extract_correlation_headers",
    "inject_correlation_headers",
    # Redaction & Size Bounding
    "redact_data",
    "redact_log_event",
    "sanitize_string",
    "is_sensitive_key",
    # OpenTelemetry Tracing
    "get_tracer",
    "init_tracer",
    "trace_span",
    "inject_traceparent",
    "extract_traceparent",
    # Honest Metrics
    "metrics",
    "get_metrics",
    "MetricsRegistry",
]
