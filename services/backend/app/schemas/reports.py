"""Pydantic schemas for synthesized research reports and citations."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CitationItem(BaseModel):
    """Grounded citation linking report claims to captured evidence."""

    marker: str
    evidence_id: str | None = None
    source_url: str | None = None


class ReportResponse(BaseModel):
    """Final synthesized research deliverable."""

    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    run_id: uuid.UUID
    title: str
    markdown_content: str
    executive_summary: str
    citations: list[dict[str, Any]]
    metadata_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
