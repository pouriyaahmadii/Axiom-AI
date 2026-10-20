"""ToolInvocation domain entity capturing tool execution telemetry, inputs, and results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid
from app.models.enums import ToolInvocationStatus

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.step import RunStep


class ToolInvocation(Base, CreatedAtMixin):
    """Execution record for an allowlisted tool invoked by the agent coordinator."""

    __tablename__ = "tool_invocations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("run_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=False,
    )
    result_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType,
        nullable=True,
    )
    status: Mapped[ToolInvocationStatus] = mapped_column(
        Enum(ToolInvocationStatus, native_enum=False, length=50),
        default=ToolInvocationStatus.INVOKED,
        nullable=False,
        index=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="tool_invocations",
    )
    step: Mapped[RunStep | None] = relationship(
        "RunStep",
        back_populates="tool_invocations",
    )

    __table_args__ = (
        Index("idx_tool_invocations_run_idempotency", "run_id", "idempotency_key"),
        Index("idx_tool_invocations_run_tool", "run_id", "tool_name"),
    )

    def __repr__(self) -> str:
        return f"<ToolInvocation(id={self.id}, tool='{self.tool_name}', status='{self.status}')>"
