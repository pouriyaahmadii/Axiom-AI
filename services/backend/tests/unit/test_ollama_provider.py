"""Unit tests for OllamaProvider local-model adapter."""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.exceptions import (
    DeterministicValidationError,
    ServiceUnavailableError,
    TransientWorkerError,
)
from app.providers.ollama import OllamaProvider
from app.schemas.llm import ExtractionOutput


def _create_mock_response(
    status_code: int = 200, content_json: dict | None = None
) -> httpx.Response:
    content_bytes = json.dumps(content_json or {}).encode("utf-8")
    return httpx.Response(
        status_code=status_code,
        content=content_bytes,
        headers={"Content-Type": "application/json"},
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )


def test_ollama_successful_extraction() -> None:
    """Verify structured extraction with mocked Ollama API response."""
    extracted_data = {
        "competitor_name": "LocalTech",
        "products": [
            {
                "name": "Local Engine",
                "description": "Offline processing daemon",
                "category": "Engine",
            }
        ],
        "pricing_summary": "Open source free",
        "target_customers": ["Developers"],
        "key_assertions": ["Zero network dependency"],
    }

    mock_body = {
        "model": "llama3.2",
        "message": {"content": json.dumps(extracted_data)},
        "done": True,
        "total_duration": 450000000,  # 450 ms in nanoseconds
        "prompt_eval_count": 80,
        "eval_count": 120,
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(200, mock_body)

    provider = OllamaProvider(model_name="llama3.2", http_client=mock_client)
    res = provider.extract_information("Sample source text about LocalTech")

    assert res.provider == "ollama"
    assert res.model == "llama3.2"
    assert isinstance(res.data, ExtractionOutput)
    assert res.data.competitor_name == "LocalTech"
    assert res.usage.prompt_tokens == 80
    assert res.usage.completion_tokens == 120
    assert res.usage.total_tokens == 200
    assert res.usage.cost_usd == Decimal("0")
    assert res.usage.latency_ms == 450.0


def test_ollama_connection_refused_raises_service_unavailable() -> None:
    """Verify unreachable Ollama daemon raises ServiceUnavailableError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.ConnectError("Connection refused to 127.0.0.1:11434")

    provider = OllamaProvider(http_client=mock_client)
    with pytest.raises(ServiceUnavailableError) as exc_info:
        provider.extract_information("Document")
    assert "ollama server is unreachable" in str(exc_info.value).lower()


def test_ollama_timeout_raises_transient_error() -> None:
    """Verify local inference timeout raises TransientWorkerError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Read timeout after 60s")

    provider = OllamaProvider(http_client=mock_client)
    with pytest.raises(TransientWorkerError) as exc_info:
        provider.extract_information("Document")
    assert "timed out" in str(exc_info.value).lower()


def test_ollama_model_not_found_404_raises_deterministic_error() -> None:
    """Verify missing model error raises DeterministicValidationError with pull advice."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(
        404, {"error": "model 'nonexistent' not found"}
    )

    provider = OllamaProvider(model_name="nonexistent", http_client=mock_client)
    with pytest.raises(DeterministicValidationError) as exc_info:
        provider.extract_information("Document")
    assert "not found" in str(exc_info.value).lower()
    assert "ollama pull" in str(exc_info.value).lower()


def test_ollama_malformed_json_raises_deterministic_error() -> None:
    """Verify malformed JSON from Ollama raises DeterministicValidationError."""
    mock_body = {
        "model": "llama3.2",
        "message": {"content": "Not JSON at all"},
        "done": True,
    }
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = _create_mock_response(200, mock_body)

    provider = OllamaProvider(http_client=mock_client)
    with pytest.raises(DeterministicValidationError) as exc_info:
        provider.extract_information("Document")
    assert "invalid json" in str(exc_info.value).lower()
