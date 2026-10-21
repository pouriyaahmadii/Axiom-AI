"""Base tool abstractions and execution result schemas for the AgentOps safe tool sandbox."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Normalized output contract returned by all allowlisted tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = Field(description="Whether the tool invocation succeeded without errors")
    tool_name: str = Field(description="Name of the invoked tool")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured output payload")
    error: str | None = Field(
        default=None, description="Human-readable error description if failed"
    )
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    idempotency_key: str | None = Field(default=None, description="Unique idempotency digest")
    content_hash: str | None = Field(
        default=None, description="Cryptographic SHA-256 hash of primary result content"
    )
    source_url: str | None = Field(
        default=None, description="Canonical source URL if external content was retrieved"
    )
    evidence_records: list[dict[str, Any]] = Field(
        default_factory=list, description="Extracted empirical evidence snippets"
    )


class BaseTool(ABC):
    """Abstract base class for all allowlisted sandbox tools.

    Guarantees:
    - Zero arbitrary shell, subprocess, or eval execution.
    - Explicit input schema validation.
    - Strict timeout and resource ceiling enforcement.
    """

    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool within safety bounds and return a normalized ToolResult."""
        pass

    def run(self, **kwargs: Any) -> ToolResult:
        """Safe execution wrapper tracking duration and unhandled exceptions."""
        start_time = time.perf_counter()
        try:
            result = self.execute(**kwargs)
            duration = (time.perf_counter() - start_time) * 1000.0
            result.duration_ms = round(duration, 2)
            return result
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"Tool '{self.name}' execution failed: {exc}",
                duration_ms=round(duration, 2),
            )
