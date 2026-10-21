"""OpenAI and OpenAI-compatible API adapter for structured generation."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    DeterministicValidationError,
    TransientWorkerError,
)
from app.providers.base import (
    BaseLLMProvider,
    sanitize_prompt_preview,
    validate_structured_output,
)
from app.schemas.llm import (
    AnalysisOutput,
    ExtractionOutput,
    LLMResponse,
    LLMUsageMetrics,
    PlanGenerationOutput,
    ReportDraftOutput,
)

logger = structlog.get_logger(__name__)
settings = get_settings()
T = TypeVar("T", bound=BaseModel)

# Token pricing per million tokens in USD
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # model_prefix: (prompt_cost_per_m, completion_cost_per_m)
    "gpt-4o-mini": (Decimal("0.150"), Decimal("0.600")),
    "gpt-4o": (Decimal("2.500"), Decimal("10.000")),
    "o1-mini": (Decimal("3.000"), Decimal("12.000")),
    "o1": (Decimal("15.000"), Decimal("60.000")),
}


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Calculate estimated cost in USD based on model token rates."""
    rate = MODEL_PRICING.get(model_name.lower())
    if not rate:
        for prefix, prefix_rate in MODEL_PRICING.items():
            if model_name.lower().startswith(prefix):
                rate = prefix_rate
                break

    if not rate:
        # Default fallback: $1.00 / 1M prompt, $3.00 / 1M completion
        rate = (Decimal("1.000"), Decimal("3.000"))

    prompt_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * rate[0]
    completion_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * rate[1]
    return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API adapter implementing structured generation via standard HTTP protocol."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        api_base: str | None = None,
        timeout: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model_name = model_name or settings.OPENAI_MODEL_NAME
        self._api_base = (api_base or settings.OPENAI_API_BASE).rstrip("/")
        self._timeout = timeout or settings.LLM_REQUEST_TIMEOUT_SECONDS
        self._http_client = http_client

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_client(self) -> httpx.Client:
        if self._http_client:
            return self._http_client
        return httpx.Client(timeout=self._timeout)

    def _call_chat_completion(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
    ) -> LLMResponse[T]:
        """Execute HTTP POST to /chat/completions with schema enforcement and error mapping."""
        if not self._api_key:
            raise AuthenticationError(
                "OpenAI API key is missing. Set OPENAI_API_KEY environment variable or pass api_key."
            )

        endpoint = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Request json_object response format with system instructions for the schema
        payload = {
            "model": self._model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        prompt_preview = sanitize_prompt_preview(messages[-1].get("content", ""))
        logger.info(
            "openai_call_started",
            model=self._model_name,
            endpoint=endpoint,
            prompt_preview=prompt_preview,
        )

        start_time = time.perf_counter()
        client = self._get_client()

        try:
            response = client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("openai_call_timeout", error=str(exc), timeout=self._timeout)
            raise TransientWorkerError(
                f"OpenAI API request timed out after {self._timeout}s: {exc}"
            ) from exc
        except httpx.NetworkError as exc:
            logger.error("openai_call_network_error", error=str(exc))
            raise TransientWorkerError(f"OpenAI API network connection error: {exc}") from exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Classify HTTP response codes
        if response.status_code == 401:
            raise AuthenticationError("OpenAI authentication failed: invalid or expired API key.")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            logger.warning("openai_rate_limited", retry_after=retry_after)
            raise TransientWorkerError(
                f"OpenAI API rate limit exceeded (HTTP 429). Retry after: {retry_after}s."
            )
        if response.status_code >= 500:
            raise TransientWorkerError(
                f"OpenAI upstream server error (HTTP {response.status_code}): {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise DeterministicValidationError(
                f"OpenAI rejected request (HTTP {response.status_code}): {response.text[:300]}"
            )

        try:
            response_json = response.json()
            raw_content = response_json["choices"][0]["message"]["content"]
        except Exception as exc:
            raise DeterministicValidationError(
                f"Failed to parse OpenAI response envelope: {exc}"
            ) from exc

        # Token accounting and cost calculation
        usage_data = response_json.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)
        cost = calculate_cost(self._model_name, prompt_tokens, completion_tokens)

        metrics = LLMUsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=round(duration_ms, 2),
        )

        logger.info(
            "openai_call_completed",
            model=self._model_name,
            total_tokens=total_tokens,
            cost_usd=str(cost),
            latency_ms=metrics.latency_ms,
        )

        # Validate structured content through the shared schema boundary
        data = validate_structured_output(raw_content, response_model)

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=metrics,
            raw_content=raw_content,
        )

    def generate_plan(
        self,
        objective: str,
        domain: str,
        geography: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> LLMResponse[PlanGenerationOutput]:
        """Synthesize a structured execution plan."""
        system_prompt = (
            "You are an expert autonomous operations planner. Synthesize a bounded, sequential plan of steps "
            "to fulfill the analytical objective using approved tools: 'web_search', 'fetch_document', 'extract_metrics'.\n"
            f"You MUST output valid JSON conforming to this schema:\n{json.dumps(PlanGenerationOutput.model_json_schema())}"
        )
        user_prompt = (
            f"Objective: {objective}\n"
            f"Domain: {domain}\n"
            f"Geography: {geography or 'Global'}\n"
            f"Constraints: {json.dumps(constraints or {})}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_chat_completion(messages, PlanGenerationOutput)

    def extract_information(
        self,
        document_text: str,
        schema_hints: dict[str, Any] | None = None,
    ) -> LLMResponse[ExtractionOutput]:
        """Extract structured entities, pricing, and claims from source text."""
        system_prompt = (
            "You are a factual research extraction engine. Extract competitor names, products/features, "
            "pricing details, target customers, and empirical factual claims from the text.\n"
            f"You MUST output valid JSON conforming to this schema:\n{json.dumps(ExtractionOutput.model_json_schema())}"
        )
        user_prompt = f"Document Text:\n{document_text}\n\nHints: {json.dumps(schema_hints or {})}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_chat_completion(messages, ExtractionOutput)

    def generate_analysis(
        self,
        extracted_data: list[dict[str, Any]],
        focus_areas: list[str] | None = None,
    ) -> LLMResponse[AnalysisOutput]:
        """Generate a competitive analysis matrix from extracted facts."""
        system_prompt = (
            "You are a principal strategy analyst. Synthesize a structured competitor analysis comparing "
            "market positions, strengths, and weaknesses from empirical evidence.\n"
            f"You MUST output valid JSON conforming to this schema:\n{json.dumps(AnalysisOutput.model_json_schema())}"
        )
        user_prompt = (
            f"Extracted Data:\n{json.dumps(extracted_data)}\n\n"
            f"Focus Areas: {json.dumps(focus_areas or [])}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_chat_completion(messages, AnalysisOutput)

    def draft_report(
        self,
        objective: str,
        analysis: dict[str, Any],
        evidence_records: list[dict[str, Any]],
    ) -> LLMResponse[ReportDraftOutput]:
        """Draft an analytical report strictly separating evidence from strategic inference."""
        system_prompt = (
            "You are a principal analyst drafting a rigorous intelligence report. "
            "Crucial: clearly separate empirical evidence from strategic inferences into dedicated sections.\n"
            f"You MUST output valid JSON conforming to this schema:\n{json.dumps(ReportDraftOutput.model_json_schema())}"
        )
        user_prompt = (
            f"Objective: {objective}\n\n"
            f"Analysis Data: {json.dumps(analysis)}\n\n"
            f"Verified Evidence Records: {json.dumps(evidence_records)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_chat_completion(messages, ReportDraftOutput)

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """Generic structured generation adhering to the specified response model."""
        sys = system_prompt or (
            "You are an AI assistant producing structured outputs. "
            f"You MUST output valid JSON conforming to this schema:\n{json.dumps(response_model.model_json_schema())}"
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt},
        ]
        return self._call_chat_completion(messages, response_model)
