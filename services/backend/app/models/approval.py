"""Approval domain entity governing human-in-the-loop (HITL) execution gates."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid
from app.models.enums import ApprovalStatus

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.step import RunStep


class Approval(Base, CreatedAtMixin):
    """Human-in-the-loop approval request gating execution of a plan, sensitive step, or final report."""

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
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("run_steps.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        default="step_execution",
        nullable=False,
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        default="",
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
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
    resolved_by: Mapped[str | None] = mapped_column(
        String(255),
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
    step: Mapped[RunStep | None] = relationship(
        "RunStep",
        back_populates="approvals",
    )

    __table_args__ = (
        Index("idx_approvals_status_created", "status", "created_at"),
        Index("idx_approvals_run_action", "run_id", "action"),
    )

    @staticmethod
    def compute_payload_hash(payload: dict[str, Any]) -> str:
        """Calculate deterministic SHA-256 hash of JSON-serialized action payload."""
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if the approval request has exceeded its expiration deadline."""
        if not self.expires_at:
            return False
        now = current_time or datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now > self.expires_at

    def matches_payload(self, current_payload: dict[str, Any]) -> bool:
        """Verify that the approval's registered payload hash matches the current action payload."""
        if not self.payload_hash:
            return True
        current_hash = self.compute_payload_hash(current_payload)
        return bool(self.payload_hash == current_hash)

    def __repr__(self) -> str:
        return f"<Approval(id={self.id}, action='{self.action}', status='{self.status}', token='{self.approval_token[:8]}...')>"
