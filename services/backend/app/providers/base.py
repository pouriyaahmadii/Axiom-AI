"""Base provider interface, shared schema validation boundary, and token accounting."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from app.core.exceptions import DeterministicValidationError
from app.schemas.llm import (
    AnalysisOutput,
    ExtractionOutput,
    LLMResponse,
    PlanGenerationOutput,
    ReportDraftOutput,
)

logger = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

# Regex to strip ```json ... ``` markdown fences if returned by a model
MARKDOWN_JSON_REGEX = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL | re.IGNORECASE)


def validate_structured_output(raw_output: str | dict[str, Any], schema: type[T]) -> T:
    """Shared schema validation boundary for all LLM providers.

    Parses raw textual JSON or dictionary data against a target Pydantic schema.
    Rejects malformed, incomplete, or ungrounded outputs deterministically with
    structured error details.

    Args:
        raw_output: String JSON or dictionary returned by the model.
        schema: Target Pydantic model class.

    Returns:
        Validated Pydantic model instance.

    Raises:
        DeterministicValidationError: If JSON is malformed or violates schema constraints.
    """
    if isinstance(raw_output, dict):
        parsed_dict = raw_output
    elif isinstance(raw_output, str):
        cleaned = raw_output.strip()
        # Strip markdown fences if present
        match = MARKDOWN_JSON_REGEX.match(cleaned)
        if match:
            cleaned = match.group(1).strip()

        try:
            parsed_dict = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning(
                "llm_output_json_decode_failed",
                schema=schema.__name__,
                error=str(exc),
                raw_preview=cleaned[:200],
            )
            raise DeterministicValidationError(
                f"Model returned invalid JSON for schema '{schema.__name__}': {exc}",
                details=[{"error": str(exc), "raw_preview": cleaned[:200]}],
            ) from exc
    else:
        raise DeterministicValidationError(
            f"Expected string or dict from provider, got {type(raw_output).__name__}"
        )

    try:
        return schema.model_validate(parsed_dict)
    except ValidationError as exc:
        logger.warning(
            "llm_output_schema_validation_failed",
            schema=schema.__name__,
            error_count=len(exc.errors()),
        )
        raise DeterministicValidationError(
            f"Model output violates schema constraints for '{schema.__name__}': {exc}",
            details=[
                {"field": err["loc"], "msg": err["msg"], "type": err["type"]}
                for err in exc.errors()
            ],
        ) from exc


def sanitize_prompt_preview(text: str, max_chars: int = 150) -> str:
    """Sanitize and truncate text for audit logging without leaking full raw context."""
    if not text:
        return ""
    # Collapse multiple whitespaces
    collapsed = " ".join(text.split())
    if len(collapsed) > max_chars:
        return f"{collapsed[:max_chars]}... [truncated {len(collapsed) - max_chars} chars]"
    return collapsed


class BaseLLMProvider(ABC):
    """Abstract interface for LLM provider adapters.

    Core business logic must interact strictly with this interface, never
    referencing vendor-specific SDK classes (OpenAI, Ollama, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g. 'mock', 'openai', 'ollama')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier (e.g. 'mock-v1', 'gpt-4o-mini', 'llama3.2')."""
        ...

    @abstractmethod
    def generate_plan(
        self,
        objective: str,
        domain: str,
        geography: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> LLMResponse[PlanGenerationOutput]:
        """Synthesize a bounded, dependency-ordered execution plan."""
        ...

    @abstractmethod
    def extract_information(
        self,
        document_text: str,
        schema_hints: dict[str, Any] | None = None,
    ) -> LLMResponse[ExtractionOutput]:
        """Extract structured entities, features, pricing, and factual claims from source text."""
        ...

    @abstractmethod
    def generate_analysis(
        self,
        extracted_data: list[dict[str, Any]],
        focus_areas: list[str] | None = None,
    ) -> LLMResponse[AnalysisOutput]:
        """Generate a strategic competitor comparison matrix from empirical evidence."""
        ...

    @abstractmethod
    def draft_report(
        self,
        objective: str,
        analysis: dict[str, Any],
        evidence_records: list[dict[str, Any]],
    ) -> LLMResponse[ReportDraftOutput]:
        """Draft a structured analytical report strictly separating evidence from inference."""
        ...

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """Generic structured generation adhering to a specific Pydantic response model."""
        ...
