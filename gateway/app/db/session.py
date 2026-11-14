from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.db.models import Base


def _create_engine(database_url: str) -> AsyncEngine:
    """Build an async engine; SQLite uses a different pool/connect profile than Postgres."""
    common = {
        # PHI safety: never echo SQL, and keep bound parameters out of exception text.
        "echo": False,
        "hide_parameters": True,
    }
    if database_url.startswith("sqlite"):
        return create_async_engine(
            database_url,
            connect_args={"check_same_thread": False},
            **common,
        )
    return create_async_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        **common,
    )


_db_url = settings.DATABASE_URL.get_secret_value()
engine: AsyncEngine = _create_engine(_db_url)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


def _ensure_correlation_id(connection: Connection) -> None:
    """Add correlation_id on databases created before Milestone 6. create_all does not alter."""
    inspector = inspect(connection)
    if not inspector.has_table("task_records"):
        return
    columns = {column["name"] for column in inspector.get_columns("task_records")}
    if "correlation_id" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE task_records ADD COLUMN correlation_id VARCHAR(64)"
        )


async def init_db() -> None:
    """Create tables if missing. Dev convenience only; replace with Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_correlation_id)
