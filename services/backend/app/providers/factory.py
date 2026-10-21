"""LLM Provider factory and explicit provider selection mechanism."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import get_settings
from app.core.exceptions import DeterministicValidationError
from app.providers.base import BaseLLMProvider
from app.providers.mock import MockLLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

SUPPORTED_LLM_PROVIDERS = {"mock", "openai", "ollama"}


def get_llm_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """Factory creating an initialized LLM provider instance based on explicit selection or environment.

    Args:
        provider_name: 'mock', 'openai', or 'ollama'. Defaults to settings.LLM_PROVIDER ('mock').
        model_name: Optional model override (e.g. 'gpt-4o-mini', 'llama3.2').
        **kwargs: Optional provider-specific overrides (api_key, api_base, http_client, seed, etc.).

    Returns:
        Instance conforming to BaseLLMProvider.

    Raises:
        DeterministicValidationError: If requested provider name is not supported.
    """
    selected = (provider_name or settings.LLM_PROVIDER).strip().lower()

    if selected not in SUPPORTED_LLM_PROVIDERS:
        supported_list = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
        logger.error("unsupported_llm_provider_requested", provider=selected)
        raise DeterministicValidationError(
            f"Unsupported LLM provider '{selected}'. Supported providers are: {supported_list}."
        )

    if selected == "mock":
        seed = kwargs.get("seed", settings.MOCK_DETERMINISTIC_SEED)
        mock_model = model_name or "mock-analytical-v1"
        return MockLLMProvider(seed=seed, model_name=mock_model)

    if selected == "openai":
        return OpenAIProvider(
            api_key=kwargs.get("api_key"),
            model_name=model_name or settings.OPENAI_MODEL_NAME,
            api_base=kwargs.get("api_base") or settings.OPENAI_API_BASE,
            timeout=kwargs.get("timeout") or settings.LLM_REQUEST_TIMEOUT_SECONDS,
            http_client=kwargs.get("http_client"),
        )

    if selected == "ollama":
        return OllamaProvider(
            base_url=kwargs.get("base_url") or settings.OLLAMA_BASE_URL,
            model_name=model_name or settings.OLLAMA_MODEL_NAME,
            timeout=kwargs.get("timeout") or settings.LLM_REQUEST_TIMEOUT_SECONDS,
            http_client=kwargs.get("http_client"),
        )

    raise DeterministicValidationError(f"Unhandled provider: {selected}")
