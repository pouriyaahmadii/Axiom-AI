"""Local Ollama model provider adapter supporting local, offline LLMs."""

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
    DeterministicValidationError,
    ServiceUnavailableError,
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


class OllamaProvider(BaseLLMProvider):
    """Local LLM provider interfacing with an Ollama daemon via native HTTP REST endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model_name = model_name or settings.OLLAMA_MODEL_NAME
        self._timeout = timeout
        self._http_client = http_client

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_client(self) -> httpx.Client:
        if self._http_client:
            return self._http_client
        return httpx.Client(timeout=self._timeout)

    def _call_ollama_chat(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
    ) -> LLMResponse[T]:
        """Execute chat request to Ollama /api/chat with format='json' and schema validation."""
        endpoint = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model_name,
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2},
        }

        prompt_preview = sanitize_prompt_preview(messages[-1].get("content", ""))
        logger.info(
            "ollama_call_started",
            model=self._model_name,
            endpoint=endpoint,
            prompt_preview=prompt_preview,
        )

        start_time = time.perf_counter()
        client = self._get_client()

        try:
            response = client.post(endpoint, json=payload)
        except httpx.ConnectError as exc:
            logger.error("ollama_connection_failed", base_url=self._base_url, error=str(exc))
            raise ServiceUnavailableError(
                f"Ollama server is unreachable at {self._base_url}. Ensure 'ollama serve' is running."
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error("ollama_call_timeout", timeout=self._timeout, error=str(exc))
            raise TransientWorkerError(
                f"Ollama inference timed out after {self._timeout}s: {exc}"
            ) from exc
        except httpx.NetworkError as exc:
            logger.error("ollama_network_error", error=str(exc))
            raise TransientWorkerError(f"Ollama communication network error: {exc}") from exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 404:
            raise DeterministicValidationError(
                f"Ollama model '{self._model_name}' was not found on {self._base_url}. Run 'ollama pull {self._model_name}'."
            )
        if response.status_code >= 500:
            raise TransientWorkerError(
                f"Ollama daemon server error (HTTP {response.status_code}): {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise DeterministicValidationError(
                f"Ollama daemon rejected request (HTTP {response.status_code}): {response.text[:300]}"
            )

        try:
            response_json = response.json()
            raw_content = response_json["message"]["content"]
        except Exception as exc:
            raise DeterministicValidationError(
                f"Failed to parse Ollama response structure: {exc}"
            ) from exc

        # Extract tokens and duration
        prompt_tokens = response_json.get("prompt_eval_count", 0)
        completion_tokens = response_json.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens

        # Ollama returns total_duration in nanoseconds
        if "total_duration" in response_json:
            reported_latency_ms = float(response_json["total_duration"]) / 1_000_000.0
        else:
            reported_latency_ms = duration_ms

        metrics = LLMUsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=Decimal("0.000000"),  # Free local compute
            latency_ms=round(reported_latency_ms, 2),
        )

        logger.info(
            "ollama_call_completed",
            model=self._model_name,
            total_tokens=total_tokens,
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
        return self._call_ollama_chat(messages, PlanGenerationOutput)

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
        return self._call_ollama_chat(messages, ExtractionOutput)

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
        return self._call_ollama_chat(messages, AnalysisOutput)

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
        return self._call_ollama_chat(messages, ReportDraftOutput)

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
        return self._call_ollama_chat(messages, response_model)
