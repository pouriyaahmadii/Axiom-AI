"""Unit tests for get_llm_provider factory and selection mechanism."""

import pytest

from app.core.exceptions import DeterministicValidationError
from app.providers.factory import get_llm_provider
from app.providers.mock import MockLLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def test_factory_default_returns_mock_provider() -> None:
    """Verify default factory call returns MockLLMProvider when configured for mock."""
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


def test_factory_explicit_mock_provider() -> None:
    """Verify explicit 'mock' selection instantiates MockLLMProvider with custom seed."""
    provider = get_llm_provider("mock", seed=999)
    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


def test_factory_explicit_openai_provider() -> None:
    """Verify explicit 'openai' selection instantiates OpenAIProvider."""
    provider = get_llm_provider("openai", api_key="sk-test", model_name="gpt-4o")
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o"


def test_factory_explicit_ollama_provider() -> None:
    """Verify explicit 'ollama' selection instantiates OllamaProvider."""
    provider = get_llm_provider("ollama", model_name="mistral", base_url="http://localhost:11434")
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_name == "ollama"
    assert provider.model_name == "mistral"


def test_factory_unsupported_provider_raises_error() -> None:
    """Verify unknown provider name raises DeterministicValidationError."""
    with pytest.raises(DeterministicValidationError) as exc_info:
        get_llm_provider("anthropic-unsupported")
    assert "unsupported llm provider" in str(exc_info.value).lower()
