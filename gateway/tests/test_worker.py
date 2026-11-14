import asyncio
import json
import uuid
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tenacity import wait_none

from app.core.redis_client import DEAD_LETTER_QUEUE, GENOMIC_QUEUE
from app.db.models import TaskRecord, TaskStatus
from app.services.ai_interface import AIService
from app.services.mock_ai_service import MockAIService
from app.workers import task_worker

SessionFactory = async_sessionmaker[AsyncSession]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

async def seed_task(factory: SessionFactory) -> uuid.UUID:
    task_id = uuid.uuid4()
    async with factory() as session:
        session.add(TaskRecord(task_id=task_id, status=TaskStatus.QUEUED, attempts=0))
        await session.commit()
    return task_id


async def load_task(factory: SessionFactory, task_id: uuid.UUID) -> TaskRecord:
    async with factory() as session:
        record = await session.get(TaskRecord, task_id)
    assert record is not None
    return record


def use_ai_service(monkeypatch: pytest.MonkeyPatch, service: AIService) -> None:
    async def fake_get_ai_service() -> AIService:
        return service

    monkeypatch.setattr(task_worker, "get_ai_service", fake_get_ai_service)


class FlakyAI:
    """Raises RuntimeError for the first `failures` calls, then succeeds."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def interpret(self, raw_data: str) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient failure")
        return {"gene": "MTHFR", "genotype": "CC", "risk": "Normal", "mock": True}


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("raw_data", "genotype", "risk"),
    [("CT", "CT", "Moderate"), ("TT", "TT", "High"), ("CC", "CC", "Normal")],
)
async def test_worker_completes_task_and_saves_mock_result(
    redis: FakeAsyncRedis,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    raw_data: str,
    genotype: str,
    risk: str,
) -> None:
    use_ai_service(monkeypatch, MockAIService(delay=0))
    task_id = await seed_task(session_factory)

    await task_worker._process_with_retries(redis, task_id, {"raw_data": raw_data})

    record = await load_task(session_factory, task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.attempts == 1
    assert record.result is not None
    assert record.result["resourceType"] == "Bundle"
    encoded = json.dumps(record.result)
    assert "MTHFR" in encoded
    assert genotype in encoded
    assert risk in encoded
    assert await redis.llen(DEAD_LETTER_QUEUE) == 0


async def test_run_worker_consumes_queue_end_to_end(
    redis: FakeAsyncRedis,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_ai_service(monkeypatch, MockAIService(delay=0))
    task_id = await seed_task(session_factory)
    await redis.lpush(
        GENOMIC_QUEUE,
        json.dumps({"task_id": str(task_id), "payload": {"raw_data": "rs1801133:TT"}}),
    )

    stop_event = asyncio.Event()
    worker = asyncio.create_task(task_worker.run_worker(redis, stop_event))
    try:
        async with asyncio.timeout(10):
            while (await load_task(session_factory, task_id)).status != TaskStatus.COMPLETED:
                await asyncio.sleep(0.05)
    finally:
        stop_event.set()
        await asyncio.wait_for(worker, timeout=10)

    record = await load_task(session_factory, task_id)
    assert record.result is not None
    assert record.result["resourceType"] == "Bundle"
    assert "High" in json.dumps(record.result)
    assert await redis.llen(GENOMIC_QUEUE) == 0


# --------------------------------------------------------------------------- #
# failure paths
# --------------------------------------------------------------------------- #

async def test_unknown_genotype_fails_immediately_without_retries(
    redis: FakeAsyncRedis,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_ai_service(monkeypatch, MockAIService(delay=0))
    task_id = await seed_task(session_factory)

    await task_worker._process_with_retries(redis, task_id, {"raw_data": "UNKNOWN"})

    record = await load_task(session_factory, task_id)
    assert record.status == TaskStatus.FAILED
    assert record.attempts == 1  # a permanent error is not retried
    assert record.result == {"error": "Input could not be interpreted"}

    assert await redis.llen(DEAD_LETTER_QUEUE) == 1
    entry = json.loads(await redis.rpop(DEAD_LETTER_QUEUE))
    assert entry["task_id"] == str(task_id)
    assert entry["error"] == "PermanentTaskError"
    assert entry["attempts"] == 1


async def test_transient_error_is_retried_then_succeeds(
    redis: FakeAsyncRedis,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(task_worker, "RETRY_WAIT", wait_none())
    flaky = FlakyAI(failures=1)
    use_ai_service(monkeypatch, flaky)
    task_id = await seed_task(session_factory)

    await task_worker._process_with_retries(redis, task_id, {"raw_data": "CC"})

    record = await load_task(session_factory, task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.attempts == 2
    assert flaky.calls == 2
    assert await redis.llen(DEAD_LETTER_QUEUE) == 0


async def test_retries_exhausted_marks_failed_and_pushes_to_dlq(
    redis: FakeAsyncRedis,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(task_worker, "RETRY_WAIT", wait_none())
    flaky = FlakyAI(failures=99)
    use_ai_service(monkeypatch, flaky)
    task_id = await seed_task(session_factory)

    await task_worker._process_with_retries(redis, task_id, {"raw_data": "CC"})

    record = await load_task(session_factory, task_id)
    assert record.status == TaskStatus.FAILED
    assert record.attempts == task_worker.MAX_ATTEMPTS == flaky.calls
    assert record.result == {"error": "Processing failed after 3 attempts"}

    entry = json.loads(await redis.rpop(DEAD_LETTER_QUEUE))
    assert entry["task_id"] == str(task_id)
    assert entry["error"] == "RuntimeError"
    assert entry["attempts"] == 3
