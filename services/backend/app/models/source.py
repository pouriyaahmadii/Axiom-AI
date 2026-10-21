"""Source domain entity representing an external URL, document, or corpus inspected during a run."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.evidence import EvidenceItem
    from app.models.run import Run


class Source(Base, CreatedAtMixin):
    """External document or endpoint retrieved and validated during research."""

    __tablename__ = "sources"

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
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    etag: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="sources",
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        "EvidenceItem",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("run_id", "url", name="uq_sources_run_url"),
        Index("idx_sources_run_domain", "run_id", "domain"),
        Index("idx_sources_run_hash", "run_id", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, run_id={self.run_id}, domain='{self.domain}')>"
