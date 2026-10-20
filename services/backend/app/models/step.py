"""RunStep domain entity representing a planned or executed step in an execution graph."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, generate_uuid
from app.models.enums import StepStatus

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.evidence import EvidenceItem
    from app.models.llm import LLMCall
    from app.models.run import Run
    from app.models.tool import ToolInvocation


class RunStep(Base, TimestampMixin):
    """Discrete execution unit scheduled or run within a Run."""

    __tablename__ = "run_steps"

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
    step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    step_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=False,
    )
    requires_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, native_enum=False, length=50),
        default=StepStatus.PENDING,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="steps",
    )
    tool_invocations: Mapped[list[ToolInvocation]] = relationship(
        "ToolInvocation",
        back_populates="step",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        "EvidenceItem",
        back_populates="step",
        lazy="selectin",
    )
    approvals: Mapped[list[Approval]] = relationship(
        "Approval",
        back_populates="step",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    llm_calls: Mapped[list[LLMCall]] = relationship(
        "LLMCall",
        back_populates="step",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_run_steps_run_step_index"),
        UniqueConstraint("run_id", "step_identifier", name="uq_run_steps_run_step_identifier"),
        Index("idx_run_steps_run_status", "run_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<RunStep(id={self.id}, run_id={self.run_id}, idx={self.step_index}, tool='{self.tool_name}')>"
