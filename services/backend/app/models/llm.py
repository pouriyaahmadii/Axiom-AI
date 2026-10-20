"""LLMCall domain entity recording inference metadata, token usage, latency, and cost."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, generate_uuid
from app.models.enums import LLMCallStatus

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.step import RunStep


class LLMCall(Base, CreatedAtMixin):
    """Auditable record of a single model inference request.

    Note: NEVER store API keys, authentication credentials, or unredacted secrets in this table.
    """

    __tablename__ = "llm_calls"

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
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(8, 6),
        default=Decimal("0.000000"),
        nullable=False,
    )
    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[LLMCallStatus] = mapped_column(
        Enum(LLMCallStatus, native_enum=False, length=50),
        default=LLMCallStatus.SUCCESS,
        nullable=False,
        index=True,
    )
    prompt_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completion_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    run: Mapped[Run] = relationship(
        "Run",
        back_populates="llm_calls",
    )
    step: Mapped[RunStep | None] = relationship(
        "RunStep",
        back_populates="llm_calls",
    )

    __table_args__ = (Index("idx_llm_calls_run_provider", "run_id", "provider"),)

    def __repr__(self) -> str:
        return f"<LLMCall(id={self.id}, model='{self.model_name}', tokens={self.total_tokens})>"
