"""Base tool abstractions and execution contracts for the AgentOps safe tool sandbox."""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, ValidationError

from app.core.exceptions import DeterministicValidationError, SecurityValidationError
from app.core.logging import get_logger
from app.tools.models import (
    ToolMetadata,
    ToolResult,
)

logger = get_logger("agentops.tools.base")

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseTool(ABC, Generic[TInput, TOutput]):
    """Abstract base class for all allowlisted tools in the AgentOps Tool Registry.

    Guarantees:
    - Zero arbitrary code, shell, or eval execution.
    - Strict typed input/output validation via Pydantic models.
    - Configurable timeouts, retry policies, and resource bounds.
    - Automatic evidence and audit record generation.
    """

    metadata: ToolMetadata

    @property
    def tool_id(self) -> str:
        """Stable unique identifier for the tool."""
        return self.metadata.tool_id

    @property
    def name(self) -> str:
        """Human-readable title of the tool."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Functional description for the orchestrator/planner."""
        return self.metadata.description

    @abstractmethod
    def execute(self, input_data: TInput, context: dict[str, Any] | None = None) -> TOutput:
        """Perform the tool's core logic using validated input parameters."""
        pass

    def run_validated(
        self,
        raw_params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Run tool with input/output validation, resource limits, and audit tracking."""
        start_time = time.perf_counter()
        ctx = context or {}

        # 1. Enforce input length ceiling
        input_str = str(raw_params)
        max_input = self.metadata.resource_limits.max_input_length
        if len(input_str) > max_input:
            duration = (time.perf_counter() - start_time) * 1000.0
            err_msg = (
                f"Input parameter payload length ({len(input_str)}) exceeds maximum allowed "
                f"limit of {max_input} characters."
            )
            logger.error("tool_input_limit_exceeded", tool_id=self.tool_id, length=len(input_str))
            return ToolResult(
                success=False,
                tool_id=self.tool_id,
                tool_name=self.name,
                error=err_msg,
                duration_ms=round(duration, 2),
            )

        # 2. Strict Input Schema Validation
        try:
            validated_input = cast(TInput, self.metadata.input_schema.model_validate(raw_params))
        except ValidationError as err:
            duration = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Input validation failed for tool '{self.tool_id}': {err}"
            logger.warning("tool_input_validation_failed", tool_id=self.tool_id, error=str(err))
            return ToolResult(
                success=False,
                tool_id=self.tool_id,
                tool_name=self.name,
                error=err_msg,
                duration_ms=round(duration, 2),
            )

        # 3. Execution with Bounded Retry Policy
        retries = 0
        max_retries = self.metadata.retry_policy.max_retries
        backoff = self.metadata.retry_policy.backoff_factor_seconds
        last_error: Exception | None = None

        while retries <= max_retries:
            try:
                output_model = self.execute(validated_input, context=ctx)
                output_dict = output_model.model_dump()
                duration = (time.perf_counter() - start_time) * 1000.0

                # 4. Enforce Output Size Limits
                output_str = str(output_dict)
                output_bytes = len(output_str.encode("utf-8"))
                max_bytes = self.metadata.resource_limits.max_output_bytes
                if output_bytes > max_bytes:
                    err_msg = f"Tool output size ({output_bytes} bytes) exceeds limit of {max_bytes} bytes."
                    logger.error(
                        "tool_output_size_exceeded", tool_id=self.tool_id, bytes=output_bytes
                    )
                    return ToolResult(
                        success=False,
                        tool_id=self.tool_id,
                        tool_name=self.name,
                        error=err_msg,
                        duration_ms=round(duration, 2),
                    )

                # 5. Output Digest and Audit Record
                content_hash = hashlib.sha256(output_str.encode("utf-8")).hexdigest()
                audit_record: dict[str, Any] = {
                    "tool_id": self.tool_id,
                    "event_type": self.metadata.audit_policy.audit_event_type,
                    "risk_level": self.metadata.risk_level.value,
                    "permission_scope": self.metadata.permission_scope,
                    "duration_ms": round(duration, 2),
                    "output_hash": content_hash,
                }
                if self.metadata.audit_policy.log_input:
                    audit_record["input_keys"] = list(raw_params.keys())

                # Collect evidence records if output contains them
                evidence_records = output_dict.get("evidence_records", [])

                return ToolResult(
                    success=True,
                    tool_id=self.tool_id,
                    tool_name=self.name,
                    data=output_dict,
                    duration_ms=round(duration, 2),
                    content_hash=content_hash,
                    source_url=output_dict.get("url") or output_dict.get("source_url"),
                    evidence_records=evidence_records,
                    audit_record=audit_record,
                )

            except (SecurityValidationError, DeterministicValidationError) as fatal_err:
                # Fatal security or deterministic errors must NEVER be retried
                duration = (time.perf_counter() - start_time) * 1000.0
                logger.error("tool_fatal_error", tool_id=self.tool_id, error=str(fatal_err))
                return ToolResult(
                    success=False,
                    tool_id=self.tool_id,
                    tool_name=self.name,
                    error=str(fatal_err),
                    duration_ms=round(duration, 2),
                )
            except Exception as exc:
                last_error = exc
                retries += 1
                if retries <= max_retries:
                    logger.warning(
                        "tool_execution_retry",
                        tool_id=self.tool_id,
                        attempt=retries,
                        max_retries=max_retries,
                        error=str(exc),
                    )
                    time.sleep(backoff * (2 ** (retries - 1)))
                else:
                    break

        duration = (time.perf_counter() - start_time) * 1000.0
        final_err_msg = f"Tool '{self.tool_id}' failed after {retries - 1} retries: {last_error}"
        logger.error(
            "tool_execution_exhausted_retries", tool_id=self.tool_id, error=str(last_error)
        )
        return ToolResult(
            success=False,
            tool_id=self.tool_id,
            tool_name=self.name,
            error=final_err_msg,
            duration_ms=round(duration, 2),
        )

    def run(self, **kwargs: Any) -> ToolResult:
        """Convenience method accepting keyword arguments directly."""
        return self.run_validated(raw_params=kwargs)
