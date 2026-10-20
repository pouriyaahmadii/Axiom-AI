"""Pytest fixtures and configuration."""

import os
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

# Ensure backend directory is in sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["SEARCH_PROVIDER"] = "mock"
os.environ["API_KEY"] = "agentops-dev-internal-key"

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_async_session  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    """Retrieve test settings."""
    return get_settings()


@pytest.fixture
def migrated_test_db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite database file and migrate it to head via Alembic."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    sync_url = f"sqlite:///{db_path}"

    # Configure Alembic to run migrations on this test file
    alembic_ini_path = backend_path / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_path / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(alembic_cfg, "head")

    yield db_path

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def migrated_db_engine(migrated_test_db_path: str) -> Generator[Engine, None, None]:
    """Provide a synchronous Engine connected to the migrated test database."""
    sync_url = f"sqlite:///{migrated_test_db_path}"
    engine = create_engine(sync_url)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_db_engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional synchronous SQLAlchemy session bound to the migrated test database."""
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


@pytest.fixture
async def async_test_engine(
    migrated_test_db_path: str,
) -> AsyncGenerator[AsyncEngine, None]:
    """Provide an asynchronous Engine connected to the migrated test database."""
    async_url = f"sqlite+aiosqlite:///{migrated_test_db_path}"
    engine = create_async_engine(async_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_db_session(
    async_test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional asynchronous SQLAlchemy session."""
    session_factory = async_sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(async_test_engine: AsyncEngine):
    """Build FastAPI test application with test database session overrides."""
    fastapi_app = create_app()

    session_factory = async_sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    async def _override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_async_session] = _override_get_async_session
    return fastapi_app


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient for FastAPI testing with internal API credentials."""
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "agentops-dev-internal-key"}
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers=headers
    ) as client:
        yield client
