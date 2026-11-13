from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.db.models import Base

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL.get_secret_value(),
    pool_size=10,
    max_overflow=20,
    pool_timeout=5,
    pool_pre_ping=True,
    pool_recycle=1800,
    # PHI safety: never echo SQL, and keep bound parameters out of exception text.
    echo=False,
    hide_parameters=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables if missing. Dev convenience only; replace with Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)