from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis, FakeServer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.workers import task_worker


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[FakeAsyncRedis]:
    # Own FakeServer per test: fakeredis otherwise shares state per host:port.
    client = FakeAsyncRedis(server=FakeServer(), decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """SQLite database (a file, so concurrent sessions get separate connections).

    The worker's `AsyncSessionLocal` is pointed at it for the duration of the test.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()
