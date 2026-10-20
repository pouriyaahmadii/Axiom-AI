"""Standardized error schemas adhering to docs/13-api-design.md."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Specific field or parameter issue explanation."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = Field(default=None, description="Affected field name if applicable")
    issue: str = Field(description="Description of the constraint or validation issue")


class ErrorPayload(BaseModel):
    """Inner error payload envelope."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Standardized machine-readable error code")
    message: str = Field(description="Human-readable safe error message")
    correlation_id: str | None = Field(
        default=None, description="Distributed correlation ID for tracing"
    )
    details: list[ErrorDetail] = Field(
        default_factory=list, description="List of granular error details"
    )


class ErrorResponse(BaseModel):
    """Top-level unified error response envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorPayload
