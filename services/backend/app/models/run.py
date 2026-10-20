"""Run domain entity representing an end-to-end bounded research task."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, generate_uuid
from app.models.enums import RunStatus

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.audit import AuditEvent
    from app.models.evidence import EvidenceItem
    from app.models.llm import LLMCall
    from app.models.report import Report
    from app.models.source import Source
    from app.models.step import RunStep
    from app.models.tool import ToolInvocation


class Run(Base, TimestampMixin):
    """Primary aggregate root representing a discrete research and analysis execution."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    objective: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    geography: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=50),
        default=RunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    llm_provider: Mapped[str] = mapped_column(
        String(50),
        default="mock",
        nullable=False,
    )
    search_provider: Mapped[str] = mapped_column(
        String(50),
        default="mock",
        nullable=False,
    )
    budget_usd_limit: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        default=Decimal("1.0000"),
        nullable=False,
    )
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    raw_plan: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType,
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    steps: Mapped[list[RunStep]] = relationship(
        "RunStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunStep.step_index",
        lazy="selectin",
    )
    tool_invocations: Mapped[list[ToolInvocation]] = relationship(
        "ToolInvocation",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sources: Mapped[list[Source]] = relationship(
        "Source",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        "EvidenceItem",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    approvals: Mapped[list[Approval]] = relationship(
        "Approval",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    report: Mapped[Report | None] = relationship(
        "Report",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    llm_calls: Mapped[list[LLMCall]] = relationship(
        "LLMCall",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_runs_status_created_at", "status", "created_at"),
        Index("idx_runs_correlation_id", "correlation_id"),
    )

    def __repr__(self) -> str:
        return f"<Run(id={self.id}, status='{self.status}', domain='{self.domain}')>"
