"""EvidenceItem domain entity preserving empirical facts and citations for report synthesis."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, JSONBType, generate_uuid

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.source import Source
    from app.models.step import RunStep


class EvidenceItem(Base, CreatedAtMixin):
    """Empirical fact, data point, or verbatim excerpt grounding factual claims."""

    __tablename__ = "evidence_items"

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
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    raw_snippet: Mapped[str] = mapped_column(
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
        back_populates="evidence_items",
    )
    step: Mapped[RunStep | None] = relationship(
        "RunStep",
        back_populates="evidence_items",
    )
    source: Mapped[Source | None] = relationship(
        "Source",
        back_populates="evidence_items",
    )

    __table_args__ = (
        UniqueConstraint("run_id", "content_hash", name="uq_evidence_items_run_content_hash"),
        Index("idx_evidence_items_source_url", "source_url"),
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceItem(id={self.id}, run_id={self.run_id}, hash='{self.content_hash[:8]}...')>"
        )
