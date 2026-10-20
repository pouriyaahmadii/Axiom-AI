"""Integration tests for Alembic database migrations."""

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
def test_migration_upgrade_and_downgrade_cycle():
    """Verify that a fresh, empty database can be migrated to head and cleanly downgraded."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    backend_root = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        # 1. Start from an empty database
        with engine.connect() as conn:
            initial_tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()
            assert len(initial_tables) == 0

        # 2. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # 3. Verify all 10 domain entity tables + alembic_version exist
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        expected_tables = {
            "alembic_version",
            "runs",
            "run_steps",
            "sources",
            "tool_invocations",
            "evidence_items",
            "approvals",
            "reports",
            "llm_calls",
            "audit_events",
            "outbox_events",
        }
        assert expected_tables.issubset(table_names), (
            f"Missing tables: {expected_tables - table_names}"
        )

        # 4. Downgrade back to base
        command.downgrade(alembic_cfg, "base")

        # 5. Verify all domain tables were dropped cleanly
        inspector = inspect(engine)
        tables_after_downgrade = set(inspector.get_table_names())
        remaining_domain_tables = tables_after_downgrade.intersection(
            expected_tables - {"alembic_version"}
        )
        assert len(remaining_domain_tables) == 0, (
            f"Leaked tables after downgrade: {remaining_domain_tables}"
        )

    finally:
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.integration
def test_migration_schema_inspection(migrated_db_engine):
    """Inspect migrated schema to verify primary keys, foreign keys, and unique constraints."""
    inspector = inspect(migrated_db_engine)

    # Inspect runs table
    run_cols = {c["name"]: c for c in inspector.get_columns("runs")}
    assert "id" in run_cols
    assert "objective" in run_cols
    assert "status" in run_cols
    assert "budget_usd_limit" in run_cols
    assert "created_at" in run_cols
    assert "updated_at" in run_cols

    run_pk = inspector.get_pk_constraint("runs")
    assert run_pk["constrained_columns"] == ["id"]

    # Inspect run_steps foreign key
    fks = inspector.get_foreign_keys("run_steps")
    fk_runs = next((fk for fk in fks if fk["referred_table"] == "runs"), None)
    assert fk_runs is not None
    assert fk_runs["constrained_columns"] == ["run_id"]
    assert fk_runs["referred_columns"] == ["id"]

    # Inspect evidence_items foreign keys
    evidence_fks = inspector.get_foreign_keys("evidence_items")
    referred_tables = {fk["referred_table"] for fk in evidence_fks}
    assert "runs" in referred_tables
