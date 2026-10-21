"""Pydantic schemas for Human-in-the-Loop (HITL) approval actions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ApprovalStatus, RunStatus


class ApprovalActionRequest(BaseModel):
    """Payload for submitting an approval verdict."""

    model_config = ConfigDict(extra="forbid")

    operator_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional explanatory notes or feedback from the human operator",
    )
    expected_payload_hash: str | None = Field(
        default=None,
        description="Optional SHA-256 payload hash verification to prevent stale authorization",
    )


class ApprovalRejectRequest(BaseModel):
    """Payload for rejecting an approval gate with a reason."""

    model_config = ConfigDict(extra="forbid")

    operator_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional feedback explaining why the proposed action was rejected",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Explicit rejection reason or rationale",
    )
    abort_run: bool = Field(
        default=True,
        description="Whether to abort the entire run or skip the gated action",
    )

    @model_validator(mode="after")
    def populate_rejection_notes(self) -> ApprovalRejectRequest:
        """Coalesce reason into operator_notes if only reason was supplied."""
        if not self.operator_notes and self.reason:
            self.operator_notes = self.reason
        return self


class ApprovalResponse(BaseModel):
    """Response returned upon creating or resolving an approval request."""

    model_config = ConfigDict(from_attributes=True)

    approval_id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    action: str = "step_execution"
    payload_hash: str = ""
    version: int = 1
    status: ApprovalStatus
    proposed_action: dict[str, Any]
    operator_notes: str | None = None
    resolved_by: str | None = None
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    run_status: RunStatus
