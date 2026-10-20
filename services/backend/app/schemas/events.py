"""Pydantic schemas for run audit and execution events."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    """Immutable audit event representation."""

    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    run_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    correlation_id: str | None = None
    event_type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """Collection of audit events for a run."""

    run_id: uuid.UUID
    items: list[AuditEventResponse]
    total: int = Field(ge=0, description="Total matching audit events")
    limit: int = Field(ge=1, le=200, description="Page limit")
    offset: int = Field(ge=0, description="Page offset")
