"""Pytest fixtures and configuration."""

import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Ensure backend directory is in sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["SEARCH_PROVIDER"] = "mock"

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    """Retrieve test settings."""
    return get_settings()


@pytest.fixture
def app():
    """Build FastAPI test application."""
    return create_app()


@pytest.fixture
async def async_client(app):
    """Provide an HTTPX AsyncClient for FastAPI testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def migrated_db_engine() -> Generator[Engine, None, None]:
    """Provide an empty SQLite database fully migrated via Alembic versioned migrations.

    NOTE: Explicitly uses Alembic 'upgrade head' rather than Base.metadata.create_all()
    to test versioned migration behavior.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    # Enable SQLite foreign key constraint enforcement
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Configure Alembic
    alembic_ini_path = backend_path / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_path / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Execute Alembic migration upgrade to head
    command.upgrade(alembic_cfg, "head")

    yield engine

    engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def db_session(migrated_db_engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session bound to the migrated test database."""
    session_factory = sessionmaker(
        bind=migrated_db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
