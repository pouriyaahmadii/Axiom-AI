"""Add attempt_count column to runs table for tracking execution attempts.

Revision ID: 0002_add_run_attempt_count
Revises: 0001_initial_domain_model
Create Date: 2026-10-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_run_attempt_count"
down_revision: str | None = "0001_initial_domain_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("runs", "attempt_count")
