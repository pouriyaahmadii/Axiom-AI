"""AuditEvent domain entity providing an immutable, tamper-resistant operational audit trail."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid

if TYPE_CHECKING:
    from app.models.run import Run


class AuditLogImmutableError(RuntimeError):
    """Raised when an attempt is made to update or delete an immutable audit record."""


class AuditEvent(Base, CreatedAtMixin):
    """Immutable log entry capturing execution state transitions and security-relevant actions.

    Audit entries are append-only; updates and deletions are explicitly prevented at the ORM layer.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("run_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(
        String(100),
        default="system",
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=False,
    )

    # Relationships
    run: Mapped[Run | None] = relationship(
        "Run",
        back_populates="audit_events",
    )

    __table_args__ = (
        Index("idx_audit_events_run_created", "run_id", "created_at"),
        Index("idx_audit_events_type_created", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, type='{self.event_type}', actor='{self.actor}')>"


# ORM-level immutability enforcement
@event.listens_for(AuditEvent, "before_update")
def _prevent_audit_event_update(_mapper: Any, _connection: Any, target: AuditEvent) -> None:
    raise AuditLogImmutableError(
        f"AuditEvent records are append-only and cannot be updated (ID: {target.id})"
    )


@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_event_delete(_mapper: Any, _connection: Any, target: AuditEvent) -> None:
    from sqlalchemy.orm import object_session

    session = object_session(target)
    if session is not None and target.run is not None and target.run in session.deleted:
        # Cascading deletion triggered by parent Run removal is permitted
        return

    raise AuditLogImmutableError(
        f"AuditEvent records are immutable and cannot be deleted individually (ID: {target.id})"
    )
