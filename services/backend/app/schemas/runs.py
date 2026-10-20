"""Pydantic schemas for research run creation, retrieval, and cancellation."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RunStatus


class RunCreateRequest(BaseModel):
    """Payload for submitting a new research or analysis run."""

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(
        min_length=10,
        max_length=2000,
        description="Natural language analytical research objective",
        examples=[
            "Analyze top 3 AI code completion tools in North America comparing features and pricing."
        ],
    )
    domain: str = Field(
        min_length=2,
        max_length=100,
        description="Subject domain or industry classification",
        examples=["software-development"],
    )
    geography: str | None = Field(
        default=None,
        max_length=100,
        description="Optional geographical target scope",
        examples=["North America"],
    )
    constraints: dict[str, Any] | None = Field(
        default=None,
        description="Optional operational or analytical constraints",
    )
    provider_override: dict[str, Any] | None = Field(
        default=None,
        description="Optional provider selection override (e.g. llm: mock, search: mock)",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Optional client-supplied idempotency key preventing duplicate submissions",
    )


class RunCreateResponse(BaseModel):
    """Response returned upon successful acceptance of a run (HTTP 202)."""

    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    status: RunStatus
    created_at: datetime


class RunSummaryResponse(BaseModel):
    """Compact summary of a run for paginated lists."""

    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    objective: str
    domain: str
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None


class RunListResponse(BaseModel):
    """Paginated collection of runs."""

    items: list[RunSummaryResponse]
    total: int = Field(ge=0, description="Total number of matching runs")
    limit: int = Field(ge=1, le=100, description="Pagination page size limit")
    offset: int = Field(ge=0, description="Pagination offset")


class StepCompactResponse(BaseModel):
    """Summary of a step included in run detail."""

    model_config = ConfigDict(from_attributes=True)

    step_id: uuid.UUID
    step_index: int
    step_identifier: str
    title: str
    tool_name: str
    status: str
    requires_human_approval: bool = False


class PlanSummaryResponse(BaseModel):
    """Execution plan representation inside RunDetailResponse."""

    total_steps: int
    steps: list[StepCompactResponse]


class ApprovalPendingResponse(BaseModel):
    """Summary of a pending approval gate on an active run."""

    approval_id: uuid.UUID
    step_id: uuid.UUID
    proposed_action: dict[str, Any]


class RunDetailResponse(BaseModel):
    """Detailed view of an individual run, its plan, and pending actions."""

    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    status: RunStatus
    objective: str
    domain: str
    geography: str | None = None
    llm_provider: str
    search_provider: str
    budget_usd_limit: Decimal
    estimated_cost_usd: Decimal
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    plan: PlanSummaryResponse | None = None
    approval_pending: ApprovalPendingResponse | None = None


class RunCancelResponse(BaseModel):
    """Response returned when an active run is cancelled."""

    run_id: uuid.UUID
    status: RunStatus
    message: str
