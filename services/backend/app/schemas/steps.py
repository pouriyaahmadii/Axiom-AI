"""Pydantic schemas for execution graph steps."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StepStatus


class RunStepResponse(BaseModel):
    """Execution step schema."""

    model_config = ConfigDict(from_attributes=True)

    step_id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    step_identifier: str
    title: str
    tool_name: str
    parameters: dict[str, Any]
    requires_human_approval: bool
    status: StepStatus
    retry_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RunStepListResponse(BaseModel):
    """Collection of steps for a given run."""

    run_id: uuid.UUID
    items: list[RunStepResponse]
    total: int = Field(ge=0, description="Total steps in this plan")
