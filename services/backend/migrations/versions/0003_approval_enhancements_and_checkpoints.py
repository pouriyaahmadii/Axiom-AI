"""Add approval enhancements and graph checkpoints table for Phase 15.

Revision ID: 0003_approval_enhancements
Revises: 0002_add_run_attempt_count
Create Date: 2026-10-21 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_approval_enhancements"
down_revision: str | None = "0002_add_run_attempt_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = (
    postgresql.JSONB(astext_type=sa.Text())
    .with_variant(sa.JSON(), "sqlite")
    .with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
)


def upgrade() -> None:
    # 1. Update approvals table with action, payload_hash, version, resolved_by
    with op.batch_alter_table("approvals", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column(
                "action",
                sa.String(length=100),
                nullable=False,
                server_default="step_execution",
            )
        )
        batch_op.add_column(
            sa.Column(
                "payload_hash",
                sa.String(length=64),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "resolved_by",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.alter_column(
            "step_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )

    # 2. Create graph_checkpoints table for durable LangGraph checkpoints
    op.create_table(
        "graph_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(length=128), nullable=True),
        sa.Column(
            "checkpoint_type", sa.String(length=50), nullable=False, server_default="langgraph"
        ),
        sa.Column("checkpoint_blob", sa.Text(), nullable=False),
        sa.Column("metadata_payload", json_type, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_graph_checkpoints_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_graph_checkpoints")),
    )
    op.create_index(
        op.f("ix_graph_checkpoints_run_id"), "graph_checkpoints", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_graph_checkpoints_checkpoint_id"),
        "graph_checkpoints",
        ["checkpoint_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("graph_checkpoints")

    with op.batch_alter_table("approvals", recreate="auto") as batch_op:
        batch_op.drop_column("resolved_by")
        batch_op.drop_column("version")
        batch_op.drop_column("payload_hash")
        batch_op.drop_column("action")
        batch_op.alter_column(
            "step_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
