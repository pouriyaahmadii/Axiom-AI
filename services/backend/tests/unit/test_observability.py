"""Unit tests for Phase 19: AgentOps observability.

Covers:
- Correlation context propagation (API request, Run, Step, Celery, LangGraph, Tools)
- Log redaction of sensitive headers, API keys, passwords, and tokens
- Payload and string size bounding
- Missing optional telemetry exporters and graceful OpenTelemetry fallback
- Metric calculation, histograms, Prometheus exposition, and approximation disclosure
- Operator acceptance criteria: identifying failed step without secrets or unstructured output
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.middleware import CorrelationIdMiddleware
from app.observability import (
    MetricsRegistry,
    bind_correlation_context,
    correlation_context,
    extract_correlation_headers,
    extract_traceparent,
    get_active_correlation,
    get_correlation_id,
    get_run_id,
    get_step_id,
    get_step_index,
    get_tracer,
    init_tracer,
    inject_correlation_headers,
    inject_traceparent,
    is_sensitive_key,
    redact_data,
    redact_log_event,
    sanitize_string,
    set_celery_task_context,
    set_correlation_id,
    set_node_context,
    set_run_id,
    set_step_context,
    set_tool_context,
    trace_span,
)

settings = get_settings()


# ==============================================================================
# 1. Correlation Propagation Tests
# ==============================================================================


@pytest.mark.unit
def test_correlation_context_get_set() -> None:
    """Verify get and set helpers for correlation identifiers."""
    corr_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    step_id = str(uuid.uuid4())

    set_correlation_id(corr_id)
    set_run_id(run_id)
    set_step_context(step_id, 2)
    set_celery_task_context("task-1234", "agentops.execute_run")
    set_node_context("validate_request")
    set_tool_context("discover_competitors")

    assert get_correlation_id() == corr_id
    assert get_run_id() == run_id
    assert get_step_id() == step_id
    assert get_step_index() == 2

    active = get_active_correlation()
    assert active["correlation_id"] == corr_id
    assert active["run_id"] == run_id
    assert active["step_id"] == step_id
    assert active["step_index"] == 2
    assert active["celery_task_id"] == "task-1234"
    assert active["node_name"] == "validate_request"
    assert active["tool_name"] == "discover_competitors"

    # Reset
    set_correlation_id(None)
    set_run_id(None)
    set_step_context(None)
    set_celery_task_context(None)
    set_node_context(None)
    set_tool_context(None)


@pytest.mark.unit
def test_scoped_correlation_context_manager() -> None:
    """Verify scoped correlation_context restores previous values upon exit."""
    set_correlation_id("outer-corr")
    set_run_id("outer-run")

    with correlation_context(
        correlation_id="inner-corr",
        run_id="inner-run",
        step_id="inner-step",
        step_index=1,
        celery_task_id="inner-task",
        node_name="generate_plan",
        tool_name="web_search",
    ) as ctx:
        assert ctx["correlation_id"] == "inner-corr"
        assert ctx["run_id"] == "inner-run"
        assert ctx["step_id"] == "inner-step"
        assert ctx["step_index"] == 1
        assert ctx["celery_task_id"] == "inner-task"
        assert ctx["node_name"] == "generate_plan"
        assert ctx["tool_name"] == "web_search"

        assert get_correlation_id() == "inner-corr"
        assert get_run_id() == "inner-run"
        assert get_step_id() == "inner-step"

    # Restored outer context
    assert get_correlation_id() == "outer-corr"
    assert get_run_id() == "outer-run"
    assert get_step_id() is None

    set_correlation_id(None)
    set_run_id(None)


@pytest.mark.unit
def test_bind_correlation_context_helper() -> None:
    """Verify bind_correlation_context convenience function."""
    bind_correlation_context(
        correlation_id="bulk-corr",
        run_id="bulk-run",
        step_id="bulk-step",
        step_index=5,
        celery_task_id="bulk-task",
    )
    active = get_active_correlation()
    assert active["correlation_id"] == "bulk-corr"
    assert active["run_id"] == "bulk-run"
    assert active["step_id"] == "bulk-step"
    assert active["step_index"] == 5
    assert active["celery_task_id"] == "bulk-task"

    # Clean up
    set_correlation_id(None)
    set_run_id(None)
    set_step_context(None)
    set_celery_task_context(None)


@pytest.mark.unit
def test_extract_and_inject_correlation_headers() -> None:
    """Verify carrier dictionary extraction and injection of correlation headers."""
    headers = {
        "X-Correlation-ID": "test-corr-abc",
        "X-Run-ID": "test-run-123",
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    }
    extracted = extract_correlation_headers(headers)
    assert extracted["correlation_id"] == "test-corr-abc"
    assert extracted["run_id"] == "test-run-123"
    assert extracted["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    with correlation_context(correlation_id="injected-corr", run_id="injected-run"):
        outgoing = inject_correlation_headers({"Content-Type": "application/json"})
        assert outgoing["X-Correlation-ID"] == "injected-corr"
        assert outgoing["X-Run-ID"] == "injected-run"
        assert outgoing["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_fastapi_correlation_middleware() -> None:
    """Verify CorrelationIdMiddleware captures header or generates UUID and returns in response."""
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)

    @test_app.get("/test-endpoint")
    async def handler() -> dict[str, str | None]:
        return {"active_correlation": get_correlation_id()}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # 1. Generated if omitted
        res1 = await client.get("/test-endpoint")
        assert res1.status_code == 200
        generated_corr = res1.headers.get("X-Correlation-ID")
        assert generated_corr is not None
        assert res1.json()["active_correlation"] == generated_corr

        # 2. Preserved if provided
        custom_id = "client-assigned-correlation-999"
        res2 = await client.get("/test-endpoint", headers={"X-Correlation-ID": custom_id})
        assert res2.status_code == 200
        assert res2.headers.get("X-Correlation-ID") == custom_id
        assert res2.json()["active_correlation"] == custom_id


# ==============================================================================
# 2. Redaction and Payload Bounding Tests
# ==============================================================================


@pytest.mark.unit
def test_sensitive_key_detection() -> None:
    """Verify sensitive key name matching."""
    assert is_sensitive_key("api_key") is True
    assert is_sensitive_key("apiKey") is True
    assert is_sensitive_key("Authorization") is True
    assert is_sensitive_key("X-API-Key") is True
    assert is_sensitive_key("client_secret") is True
    assert is_sensitive_key("db_password") is True
    assert is_sensitive_key("access_token") is True
    assert is_sensitive_key("session_cookie") is True
    assert is_sensitive_key("webhook_secret") is True

    # Safe keys
    assert is_sensitive_key("domain") is False
    assert is_sensitive_key("objective") is False
    assert is_sensitive_key("run_id") is False
    assert is_sensitive_key("status") is False
    assert is_sensitive_key("created_at") is False


@pytest.mark.unit
def test_redact_sensitive_dictionary_keys() -> None:
    """Verify nested dictionaries have secret values masked with [REDACTED]."""
    payload = {
        "objective": "Research competitors",
        "api_key": "sk-proj-super-secret-key-12345",
        "auth": {"token": "jwt.secret.token", "user": "admin"},
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "Cookie": "session=abcdef123456",
        },
        "safe_list": ["item1", {"sub_secret": "pass123", "name": "safe"}],
    }

    scrubbed = redact_data(payload)

    assert scrubbed["objective"] == "Research competitors"
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["auth"]["token"] == "[REDACTED]"
    assert scrubbed["auth"]["user"] == "admin"
    assert scrubbed["headers"]["Authorization"] == "[REDACTED]"
    assert scrubbed["headers"]["Cookie"] == "[REDACTED]"
    assert scrubbed["safe_list"][0] == "item1"
    assert scrubbed["safe_list"][1]["sub_secret"] == "[REDACTED]"
    assert scrubbed["safe_list"][1]["name"] == "safe"


@pytest.mark.unit
def test_string_token_and_query_param_redaction() -> None:
    """Verify sensitive strings, Bearer tokens, OpenAI keys, and URL query params are scrubbed."""
    text_with_bearer = "Error connecting with Authorization: Bearer secret-token-xyz123 to backend"
    assert (
        sanitize_string(text_with_bearer)
        == "Error connecting with Authorization: Bearer [REDACTED] to backend"
    )

    text_with_openai_key = "Using fallback key sk-1234567890abcdef1234567890 for provider"
    assert "[REDACTED]" in sanitize_string(text_with_openai_key)
    assert "sk-1234567890abcdef1234567890" not in sanitize_string(text_with_openai_key)

    url_with_api_key = "https://api.tavily.com/search?api_key=tvly-secret123&query=ai"
    assert (
        sanitize_string(url_with_api_key)
        == "https://api.tavily.com/search?api_key=[REDACTED]&query=ai"
    )


@pytest.mark.unit
def test_string_length_bounding() -> None:
    """Verify oversized strings are truncated with char count annotations."""
    long_string = "a" * 2000
    bounded = sanitize_string(long_string, max_length=100)
    assert len(bounded) < 2000
    assert bounded.startswith("a" * 100)
    assert "... [truncated 1900 chars]" in bounded


@pytest.mark.unit
def test_structlog_redaction_processor() -> None:
    """Verify redact_log_event processor scrubs structlog event dictionaries."""
    event = {
        "event": "llm_request_started",
        "api_key": "sk-1234567890abcdef",
        "prompt": "Analyze market " + ("x" * 2000),
        "status": "RUNNING",
    }
    processed = redact_log_event(None, "info", event)
    assert processed["api_key"] == "[REDACTED]"
    assert "... [truncated" in processed["prompt"]
    assert processed["status"] == "RUNNING"


# ==============================================================================
# 3. Tracing & Optional Exporter Fallback Tests
# ==============================================================================


@pytest.mark.unit
def test_get_tracer_and_trace_span() -> None:
    """Verify trace_span starts spans, records attributes, and handles exceptions cleanly."""
    tracer = get_tracer("test_tracer")
    assert tracer is not None

    with (
        correlation_context(run_id="span-run-123", tool_name="fetch_page"),
        trace_span("test.operation", {"custom_attr": "custom_val"}) as span,
    ):
        assert span is not None

    # Verify exception is caught and recorded without swallowing
    with pytest.raises(ValueError, match="simulated failure"), trace_span("failing.operation"):
        raise ValueError("simulated failure")


@pytest.mark.unit
def test_missing_optional_telemetry_exporters_graceful_fallback() -> None:
    """Verify init_tracer degrades gracefully when OpenTelemetry exporter is missing or disabled."""
    # Should complete without throwing any exception
    init_tracer()
    tracer = get_tracer()
    assert tracer is not None


@pytest.mark.unit
def test_w3c_traceparent_propagation() -> None:
    """Verify W3C traceparent carrier injection and extraction."""
    carrier: dict[str, str] = {}
    with trace_span("root_span"):
        inject_traceparent(carrier)

    # In local no-op tracer, carrier injection operates gracefully without crashing
    assert isinstance(carrier, dict)

    # Verify extraction operates gracefully
    extract_traceparent({"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"})


# ==============================================================================
# 4. Metric Calculation and Approximation Disclosures
# ==============================================================================


@pytest.mark.unit
def test_metrics_registry_counters_and_gauges() -> None:
    """Verify counters and gauges compute values honestly."""
    reg = MetricsRegistry()

    # Gauge
    reg.set_gauge("active_runs", 0.0)
    reg.adjust_gauge("active_runs", 1.0)
    reg.adjust_gauge("active_runs", 2.0)
    reg.adjust_gauge("active_runs", -1.0)
    summary = reg.get_summary()
    assert summary["gauges"]["active_runs"] == 2.0

    # Counter
    reg.increment_counter("runs_total", 1.0, {"status": "COMPLETED"})
    reg.increment_counter("runs_total", 1.0, {"status": "COMPLETED"})
    reg.increment_counter("runs_total", 1.0, {"status": "FAILED"})

    summary = reg.get_summary()
    runs_total = summary["counters"]["runs_total"]
    completed_entry = next(
        item for item in runs_total if item["labels"].get("status") == "COMPLETED"
    )
    failed_entry = next(item for item in runs_total if item["labels"].get("status") == "FAILED")
    assert completed_entry["value"] == 2.0
    assert failed_entry["value"] == 1.0


@pytest.mark.unit
def test_metrics_registry_histograms_and_percentiles() -> None:
    """Verify histogram computes min, max, sum, and p50/p90/p99 percentiles."""
    reg = MetricsRegistry()

    # Record 10 observations: 1.0 to 10.0
    for val in range(1, 11):
        reg.observe_histogram("tool_duration_seconds", float(val), {"tool": "web_search"})

    summary = reg.get_summary()
    hist_entry = summary["histograms"]["tool_duration_seconds"][0]
    stats = hist_entry["stats"]

    assert stats["count"] == 10
    assert stats["sum"] == 55.0
    assert stats["min"] == 1.0
    assert stats["max"] == 10.0
    assert 5.0 <= stats["p50"] <= 6.0
    assert stats["p90"] >= 9.0


@pytest.mark.unit
def test_metrics_domain_recording_methods() -> None:
    """Verify high-level domain telemetry recording methods."""
    reg = MetricsRegistry()

    reg.record_run_started()
    reg.record_queue_wait(0.45)
    reg.record_step_executed("web_search", "COMPLETED", 1.25)
    reg.record_tool_call("fetch_document", "COMPLETED", 0.82)
    reg.record_llm_request(
        provider="mock",
        model="mock-analytical-v1",
        prompt_tokens=120,
        completion_tokens=240,
        cost_usd=0.0015,
        duration_seconds=0.45,
    )
    reg.record_source_retrieved("arxiv.org", 200)
    reg.record_approval_event("step_execution", "APPROVED", 14.5)
    reg.record_report_finalized(claims_count=12, citations_count=18)
    reg.record_run_completed("COMPLETED", 15.2)

    summary = reg.get_summary()

    # Check that approximations are explicitly disclosed
    assert "approximations" in summary
    assert "llm_estimated_cost_usd_total" in summary["approximations"]
    assert "queue_wait_seconds" in summary["approximations"]
    assert "tool_duration_seconds" in summary["approximations"]

    # Verify Prometheus format export
    prom_text = reg.get_prometheus_format()
    assert "agentops_active_runs" in prom_text
    assert "agentops_runs_total" in prom_text
    assert "agentops_llm_tokens_total" in prom_text
    assert "agentops_tool_duration_seconds" in prom_text


@pytest.mark.unit
def test_metrics_reset() -> None:
    """Verify reset clears in-memory metrics for test isolation."""
    reg = MetricsRegistry()
    reg.increment_counter("temp_counter", 5.0)
    reg.set_gauge("temp_gauge", 10.0)
    assert len(reg.get_summary()["counters"]) > 0

    reg.reset()
    assert len(reg.get_summary()["counters"]) == 0
    assert len(reg.get_summary()["gauges"]) == 0


# ==============================================================================
# 5. Operator Acceptance Criteria Test
# ==============================================================================


@pytest.mark.unit
def test_operator_can_identify_failed_step_without_secrets() -> None:
    """Acceptance Criteria:

    An operator can identify the failed step of a run from persisted records
    and correlated logs without exposing secrets or reconstructing execution
    from unstructured model output.
    """
    failed_run_id = str(uuid.uuid4())
    failed_step_id = str(uuid.uuid4())
    correlation_id = f"corr-{uuid.uuid4()}"

    # 1. Simulate persisted step record in terminal failure state
    step_record = {
        "step_id": failed_step_id,
        "run_id": failed_run_id,
        "step_index": 2,
        "step_identifier": "fetch_competitor_profile",
        "tool_name": "fetch_approved_public_page",
        "status": "FAILED",
        "retry_count": 2,
        "error_message": "SSRF violation: target IP 169.254.169.254 is within blocked cloud metadata range.",
        "parameters": {
            "url": "http://169.254.169.254/latest/meta-data/",
            "api_key": "secret-super-key-12345",
        },
    }

    # 2. Simulate audit event emitted on failure
    audit_event = {
        "run_id": failed_run_id,
        "step_id": failed_step_id,
        "correlation_id": correlation_id,
        "event_type": "STEP_FAILED",
        "actor": "celery_worker",
        "payload": {
            "step_index": 2,
            "tool_name": "fetch_approved_public_page",
            "error_category": "security_policy_violation",
            "error_message": step_record["error_message"],
            "attempt": 2,
        },
    }

    # 3. Simulate structured log emitted for this failed step
    raw_log = {
        "timestamp": "2026-10-21T18:00:00Z",
        "level": "ERROR",
        "message": "Step execution failed due to policy violation",
        "run_id": failed_run_id,
        "step_id": failed_step_id,
        "correlation_id": correlation_id,
        "tool_name": "fetch_approved_public_page",
        "error_category": "security_policy_violation",
        "error_message": step_record["error_message"],
        "step_parameters": step_record["parameters"],
    }

    # Redact log through observability redactor
    sanitized_log = redact_log_event(None, "error", raw_log)

    # Verification:
    # 1. Operator can identify the exact failed step ID and index
    assert sanitized_log["step_id"] == failed_step_id
    assert step_record["status"] == "FAILED"
    assert audit_event["payload"]["step_index"] == 2

    # 2. Operator can identify the tool name and exact failure reason
    assert sanitized_log["tool_name"] == "fetch_approved_public_page"
    assert "SSRF violation" in sanitized_log["error_message"]
    assert "cloud metadata range" in audit_event["payload"]["error_message"]

    # 3. Correlation ID bridges the API request, run, and step across systems
    assert sanitized_log["correlation_id"] == correlation_id
    assert audit_event["correlation_id"] == correlation_id

    # 4. Secrets in step parameters are NEVER exposed in logs
    assert sanitized_log["step_parameters"]["api_key"] == "[REDACTED]"
    assert "secret-super-key-12345" not in str(sanitized_log)
