"""OpenTelemetry-compatible tracing layer with W3C propagation and graceful fallbacks."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.config import get_settings
from app.observability.context import get_active_correlation

logger = structlog.get_logger(__name__)
settings = get_settings()

_PROPAGATOR = TraceContextTextMapPropagator()
_TRACER_INITIALIZED = False


def init_tracer() -> None:
    """Initialize OpenTelemetry tracer provider if enabled, with graceful fallback on missing exporters."""
    global _TRACER_INITIALIZED
    if _TRACER_INITIALIZED:
        return

    _TRACER_INITIALIZED = True

    if not settings.OTEL_ENABLED:
        logger.debug("opentelemetry_tracing_disabled", mode="local_noop")
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": settings.APP_NAME,
                "service.environment": settings.ENVIRONMENT,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(
            "opentelemetry_tracing_initialized",
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        )
    except (ImportError, Exception) as exc:
        logger.info(
            "opentelemetry_sdk_or_exporter_unavailable",
            reason=str(exc),
            fallback="Using NoOp/In-Memory OpenTelemetry Tracer",
        )


def get_tracer(name: str = "agentops") -> trace.Tracer:
    """Retrieve an OpenTelemetry-compatible tracer."""
    init_tracer()
    return trace.get_tracer(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Generator[Span, None, None]:
    """Context manager for tracing operations with automatic correlation and error recording."""
    tracer = get_tracer()
    attrs = dict(attributes or {})

    # Auto-inject active correlation identifiers
    active_corr = get_active_correlation()
    for k, v in active_corr.items():
        if v is not None and k not in attrs:
            attrs[f"agentops.{k}"] = str(v)

    with tracer.start_as_current_span(name, attributes=attrs, kind=kind) as span:
        # Bind span and trace IDs to structlog context if valid
        span_ctx = span.get_span_context()
        if span_ctx and span_ctx.is_valid:
            trace_id_hex = trace.format_trace_id(span_ctx.trace_id)
            span_id_hex = trace.format_span_id(span_ctx.span_id)
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id_hex,
                span_id=span_id_hex,
            )

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, description=str(exc))
            raise


def inject_traceparent(carrier: dict[str, str]) -> dict[str, str]:
    """Inject active W3C traceparent and tracestate into a carrier dictionary."""
    _PROPAGATOR.inject(carrier)
    return carrier


def extract_traceparent(carrier: dict[str, str]) -> None:
    """Extract W3C traceparent into the current thread/async context."""
    ctx = _PROPAGATOR.extract(carrier)
    trace.set_span_in_context(trace.get_current_span(ctx))
