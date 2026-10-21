"""Typed models, policies, and schemas for the AgentOps safe tool sandbox."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """Risk classification determining oversight and approval requirements."""

    LOW = "low"  # Read-only internal queries, deterministic transforms
    MEDIUM = "medium"  # External read-only retrieval, search
    HIGH = "high"  # High-impact operations, large context synthesis, data mutation


class RetryPolicy(BaseModel):
    """Declarative retry policy for transient tool failures."""

    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(default=2, ge=0, le=5, description="Maximum retry attempts")
    backoff_factor_seconds: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Exponential backoff base in seconds"
    )
    retryable_error_categories: list[str] = Field(
        default_factory=lambda: ["TimeoutError", "TransientNetworkError", "RateLimitError"],
        description="Error classification names eligible for retry",
    )


class ResourceLimits(BaseModel):
    """Execution bounds preventing denial of service or resource exhaustion."""

    model_config = ConfigDict(frozen=True)

    max_input_length: int = Field(
        default=50_000, description="Maximum allowable characters in input payload"
    )
    max_output_bytes: int = Field(
        default=1_048_576, description="Maximum allowable output size in bytes (1 MB default)"
    )
    max_execution_seconds: float = Field(
        default=30.0, ge=1.0, le=120.0, description="Hard timeout ceiling for tool execution"
    )


class AuditPolicy(BaseModel):
    """Audit logging and telemetry specifications for compliance tracking."""

    model_config = ConfigDict(frozen=True)

    log_input: bool = Field(
        default=True, description="Whether to record input parameters in audit logs"
    )
    log_output_digest: bool = Field(
        default=True, description="Whether to compute and record SHA-256 digest of output"
    )
    mask_sensitive: bool = Field(
        default=True, description="Whether to mask tokens, API keys, or credentials"
    )
    audit_event_type: str = Field(
        default="TOOL_INVOCATION", description="Standard event category for audit event trail"
    )


class ToolMetadata(BaseModel):
    """Comprehensive specification defining an approved tool in the Tool Registry."""

    tool_id: str = Field(min_length=2, max_length=64, description="Stable unique tool identifier")
    name: str = Field(min_length=2, max_length=100, description="Human-readable tool title")
    description: str = Field(min_length=10, max_length=500, description="Functional summary")
    input_schema: type[BaseModel] = Field(description="Typed Pydantic class validating tool inputs")
    output_schema: type[BaseModel] = Field(
        description="Typed Pydantic class validating tool outputs"
    )
    timeout_seconds: float = Field(
        default=15.0, ge=1.0, le=120.0, description="Per-invocation timeout"
    )
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    requires_approval: bool = Field(
        default=False, description="Whether operator approval is required before execution"
    )
    permission_scope: str = Field(
        default="research:read", description="Security capability required to invoke this tool"
    )
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    audit_policy: AuditPolicy = Field(default_factory=AuditPolicy)


class ToolResult(BaseModel):
    """Normalized result returned from all tool registry invocations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = Field(
        description="Whether invocation completed without policy or runtime errors"
    )
    tool_id: str = Field(description="Identifier of the executed tool")
    tool_name: str = Field(default="", description="Name of the executed tool")
    data: dict[str, Any] = Field(default_factory=dict, description="Typed output dictionary")
    error: str | None = Field(default=None, description="Detailed error description if failed")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    idempotency_key: str | None = Field(default=None, description="Unique idempotency digest")
    content_hash: str | None = Field(
        default=None, description="Cryptographic SHA-256 hash of output data"
    )
    source_url: str | None = Field(default=None, description="Canonical source URL if external")
    evidence_records: list[dict[str, Any]] = Field(
        default_factory=list, description="Verifiable empirical evidence records"
    )
    audit_record: dict[str, Any] = Field(
        default_factory=dict, description="Structured audit log entry"
    )
