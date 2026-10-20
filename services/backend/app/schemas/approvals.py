"""Pydantic schemas for Human-in-the-Loop (HITL) approval actions."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApprovalStatus, RunStatus


class ApprovalActionRequest(BaseModel):
    """Payload for submitting an approval verdict."""

    model_config = ConfigDict(extra="forbid")

    operator_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional explanatory notes or feedback from the human operator",
    )


class ApprovalRejectRequest(BaseModel):
    """Payload for rejecting an approval gate."""

    model_config = ConfigDict(extra="forbid")

    operator_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional feedback explaining why the proposed action was rejected",
    )
    abort_run: bool = Field(
        default=True,
        description="Whether to abort the entire run or skip the gated step",
    )


class ApprovalResponse(BaseModel):
    """Response returned upon resolving an approval request."""

    model_config = ConfigDict(from_attributes=True)

    approval_id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    status: ApprovalStatus
    proposed_action: dict[str, Any]
    operator_notes: str | None = None
    resolved_at: datetime | None = None
    run_status: RunStatus
