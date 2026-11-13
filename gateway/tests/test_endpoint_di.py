import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.endpoints import router
from app.core.redis_client import GENOMIC_QUEUE, get_redis
from app.db.models import TaskRecord, TaskStatus
from app.db.session import get_db
from app.services.ai_interface import AIService
from app.services.dependencies import get_ai_service


class StubAI:
    def __init__(self) -> None:
        self.calls = 0

    async def interpret(self, raw_data: str) -> dict[str, Any]:
        self.calls += 1
        return {}


async def test_endpoint_resolves_ai_service_but_leaves_processing_to_worker(
    redis: FakeAsyncRedis, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    stub = StubAI()
    resolved = 0

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_redis() -> Redis:
        return redis

    async def override_ai() -> AIService:
        nonlocal resolved
        resolved += 1
        return stub

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_ai_service] = override_ai

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/genomic-interpretations",
            json={
                "patient_reference": "Patient/123",
                "specimen_reference": "Specimen/9",
                "raw_data": "rs1801133:CT",
                "callback_url": "https://lis.example.org/cb",
            },
            headers={"Idempotency-Key": "di-test-1"},
        )

    assert response.status_code == 202
    assert resolved == 1  # DI is wired into the endpoint...
    assert stub.calls == 0  # ...but interpretation is left to the worker

    task_id = uuid.UUID(response.headers["Location"].rsplit("/", 1)[1])
    async with session_factory() as session:
        record = await session.get(TaskRecord, task_id)
    assert record is not None
    assert record.status == TaskStatus.QUEUED

    message = json.loads(await redis.rpop(GENOMIC_QUEUE))
    assert message["task_id"] == str(task_id)
    assert message["payload"]["raw_data"] == "rs1801133:CT"
