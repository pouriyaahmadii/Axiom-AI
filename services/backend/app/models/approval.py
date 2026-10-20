"""Approval domain entity governing human-in-the-loop (HITL) execution gates."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid
from app.models.enums import ApprovalStatus

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.step import RunStep


class Approval(Base, CreatedAtMixin):
    """Human-in-the-loop approval request gating execution of a sensitive step."""

    __tablename__ = "approvals"

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
    step_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("run_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approval_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False, length=50),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    proposed_action: Mapped[dict[str, Any]] = mapped_column(
        JSONBType,
        nullable=False,
    )
    operator_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="approvals",
    )
    step: Mapped[RunStep] = relationship(
        "RunStep",
        back_populates="approvals",
    )

    __table_args__ = (
        UniqueConstraint("run_id", "step_id", name="uq_approvals_run_step"),
        Index("idx_approvals_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Approval(id={self.id}, status='{self.status}', token='{self.approval_token[:8]}...')>"
