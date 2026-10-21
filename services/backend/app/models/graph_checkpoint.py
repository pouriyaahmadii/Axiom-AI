"""GraphCheckpoint domain entity storing durable LangGraph checkpoints in PostgreSQL."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid

if TYPE_CHECKING:
    from app.models.run import Run


class GraphCheckpoint(Base, CreatedAtMixin):
    """Durable checkpoint snapshot of a LangGraph execution state for human-in-the-loop and crash recovery."""

    __tablename__ = "graph_checkpoints"

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
    checkpoint_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    parent_checkpoint_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    checkpoint_type: Mapped[str] = mapped_column(
        String(50),
        default="langgraph",
        nullable=False,
    )
    checkpoint_blob: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=False,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="graph_checkpoints",
    )

    __table_args__ = (
        Index("idx_graph_checkpoints_run_checkpoint", "run_id", "checkpoint_id"),
        Index("idx_graph_checkpoints_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<GraphCheckpoint(id={self.id}, run_id={self.run_id}, checkpoint_id='{self.checkpoint_id}')>"
