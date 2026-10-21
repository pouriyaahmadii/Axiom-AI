"""Unit tests for OpenAIProvider: structured outputs, error mapping, timeouts, and cost accounting."""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.exceptions import (
    AuthenticationError,
    DeterministicValidationError,
    TransientWorkerError,
)
from app.providers.openai import OpenAIProvider, calculate_cost
from app.schemas.llm import PlanGenerationOutput


def _create_mock_response(
    status_code: int = 200, content_json: dict | None = None, headers: dict | None = None
) -> httpx.Response:
    content_bytes = json.dumps(content_json or {}).encode("utf-8")
    return httpx.Response(
        status_code=status_code,
        content=content_bytes,
        headers=headers or {"Content-Type": "application/json"},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def test_openai_missing_api_key_raises_authentication_error() -> None:
    """Verify missing API key raises AuthenticationError."""
    provider = OpenAIProvider(api_key=None)
    # Ensure environment key is not picked up
    provider._api_key = None

    with pytest.raises(AuthenticationError) as exc_info:
        provider.generate_plan("Test objective", domain="fintech")
    assert "API key is missing" in str(exc_info.value)


def test_openai_successful_structured_plan_generation() -> None:
    """Verify structured plan generation with mocked HTTP response and token accounting."""
    plan_data = {
        "objective": "Analyze competitor landscape",
        "domain": "software",
        "steps": [
            {
                "step_index": 1,
                "step_identifier": "search_step",
                "title": "Search market",
                "tool_name": "web_search",
                "parameters": {"query": "software competitors"},
                "requires_human_approval": False,
            }
        ],
        "estimated_complexity": "low",
        "rationale": "Direct single search",
    }

    mock_body = {
        "choices": [{"message": {"content": json.dumps(plan_data)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(200, mock_body)

    provider = OpenAIProvider(
        api_key="sk-test-key-12345", model_name="gpt-4o-mini", http_client=mock_client
    )
    res = provider.generate_plan("Analyze competitor landscape", domain="software")

    assert res.provider == "openai"
    assert res.model == "gpt-4o-mini"
    assert isinstance(res.data, PlanGenerationOutput)
    assert res.data.domain == "software"
    assert len(res.data.steps) == 1
    assert res.usage.prompt_tokens == 100
    assert res.usage.completion_tokens == 50
    assert res.usage.total_tokens == 150
    assert res.usage.cost_usd > Decimal("0")


def test_openai_timeout_raises_transient_error() -> None:
    """Verify request timeout raises TransientWorkerError for retry handling."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Read timed out")

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(TransientWorkerError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "timed out" in str(exc_info.value).lower()


def test_openai_rate_limit_429_raises_transient_error() -> None:
    """Verify HTTP 429 raises TransientWorkerError with retry information."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(
        429, {"error": "Rate limit exceeded"}, headers={"Retry-After": "20"}
    )

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(TransientWorkerError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "rate limit" in str(exc_info.value).lower()
    assert "20" in str(exc_info.value)


def test_openai_upstream_500_raises_transient_error() -> None:
    """Verify HTTP 500 server error raises TransientWorkerError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(500, {"error": "Internal server error"})

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(TransientWorkerError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "upstream server error" in str(exc_info.value).lower()


def test_openai_bad_request_400_raises_deterministic_error() -> None:
    """Verify HTTP 400 client error raises DeterministicValidationError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(400, {"error": "Invalid parameter model"})

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(DeterministicValidationError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "rejected request" in str(exc_info.value).lower()


def test_openai_malformed_json_content_raises_deterministic_error() -> None:
    """Verify malformed JSON from model raises DeterministicValidationError."""
    mock_body = {
        "choices": [{"message": {"content": "This is plain text, not valid JSON {"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(200, mock_body)

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(DeterministicValidationError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "invalid json" in str(exc_info.value).lower()


def test_openai_schema_violation_raises_deterministic_error() -> None:
    """Verify missing required fields in JSON raises DeterministicValidationError."""
    mock_body = {
        # Missing required 'steps' field
        "choices": [{"message": {"content": json.dumps({"objective": "Missing steps"})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(200, mock_body)

    provider = OpenAIProvider(api_key="sk-test-key", http_client=mock_client)
    with pytest.raises(DeterministicValidationError) as exc_info:
        provider.generate_plan("Test", domain="tech")
    assert "schema constraints" in str(exc_info.value).lower()


def test_cost_calculation_rates() -> None:
    """Verify token cost calculation for gpt-4o-mini and fallbacks."""
    # gpt-4o-mini: 1M in = $0.150, 1M out = $0.600
    cost_mini = calculate_cost("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost_mini == Decimal("0.750000")

    # Small token count
    small_cost = calculate_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    assert small_cost > Decimal("0")
