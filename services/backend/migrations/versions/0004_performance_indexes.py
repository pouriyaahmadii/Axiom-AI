"""Add performance indexes for Phase 21.

Revision ID: 0004_performance_indexes
Revises: 0003_approval_enhancements
Create Date: 2026-10-21 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_performance_indexes"
down_revision: str | None = "0003_approval_enhancements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Composite index for source deduplication lookups
    op.create_index(
        "idx_sources_run_hash",
        "sources",
        ["run_id", "content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_sources_run_hash", table_name="sources")
