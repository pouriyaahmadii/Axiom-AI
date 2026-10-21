"""Correlation ID and request lifecycle middleware."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.context import correlation_context
from app.observability.tracer import extract_traceparent, trace_span


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensures every incoming request carries a correlation ID propagated across logs and responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Extract existing header or generate a new UUIDv4
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        # Extract W3C trace context if present
        traceparent = request.headers.get("traceparent")
        if traceparent:
            extract_traceparent({"traceparent": traceparent})

        start_time = time.perf_counter()
        with (
            correlation_context(correlation_id=correlation_id),
            trace_span(
                "http.request",
                {
                    "http.method": request.method,
                    "http.path": request.url.path,
                    "http.route": request.url.path,
                },
            ) as span,
        ):
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration_ms", round(duration_ms, 2))

        response.headers["X-Correlation-ID"] = correlation_id
        return response
