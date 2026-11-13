import asyncio
import functools
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import update
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.redis_client import DEAD_LETTER_QUEUE, GENOMIC_QUEUE
from app.db.models import TaskRecord, TaskStatus
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 5
MAX_ATTEMPTS = 3
BRPOP_TIMEOUT_SECONDS = 1  # short, so the loop notices the stop event quickly
SHUTDOWN_GRACE_SECONDS = 15

# Dev-only hook to exercise the retry/DLQ path: send raw_data == this value.
_FORCE_FAIL_MARKER = "FORCE_FAIL"


class TaskNotFound(Exception):
    """Queue message references a task that no longer exists in the DB."""


# --------------------------------------------------------------------------- #
# Worker loop
# --------------------------------------------------------------------------- #

async def run_worker(redis: Redis, stop_event: asyncio.Event) -> None:
    """Consume `genomic_queue` until `stop_event` is set.

    The semaphore is acquired BEFORE BRPOP so we never pop a job we can't start
    immediately (a popped-but-waiting job would be lost on shutdown).
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    in_flight: set[asyncio.Task[None]] = set()
    logger.info("Worker started (concurrency=%d)", MAX_CONCURRENCY)

    try:
        while not stop_event.is_set():
            await semaphore.acquire()
            try:
                raw = await _pop_job(redis)
            except BaseException:
                semaphore.release()
                raise
            if raw is None:
                semaphore.release()
                continue

            job = asyncio.create_task(_handle_job(redis, raw, semaphore))
            in_flight.add(job)
            job.add_done_callback(in_flight.discard)
    finally:
        if in_flight:
            logger.info("Worker draining %d in-flight job(s)", len(in_flight))
            _, pending = await asyncio.wait(in_flight, timeout=SHUTDOWN_GRACE_SECONDS)
            for job in pending:
                job.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        logger.info("Worker stopped")


async def _pop_job(redis: Redis) -> str | None:
    try:
        item = await redis.brpop([GENOMIC_QUEUE], timeout=BRPOP_TIMEOUT_SECONDS)
    except RedisError as exc:
        logger.error("BRPOP failed (%s); backing off", type(exc).__name__)
        await asyncio.sleep(1)
        return None
    return item[1] if item else None


async def _handle_job(redis: Redis, raw: str, semaphore: asyncio.Semaphore) -> None:
    try:
        try:
            task_id, payload = _parse_message(raw)
        except ValueError:
            logger.error("Malformed queue message moved to DLQ")
            await _push_dlq(redis, {"raw": raw, "error": "MalformedMessage"})
            return
        await _process_with_retries(redis, task_id, payload)
    except Exception as exc:  # last line of defence; the loop must survive
        logger.error("Unhandled worker error (%s)", type(exc).__name__)
    finally:
        semaphore.release()


def _parse_message(raw: str) -> tuple[uuid.UUID, dict[str, Any]]:
    try:
        message = json.loads(raw)
        task_id = uuid.UUID(message["task_id"])
        payload = message["payload"]
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed message") from exc
    if not isinstance(payload, dict):
        raise ValueError("malformed message")
    return task_id, payload


# --------------------------------------------------------------------------- #
# Processing, retries, DLQ
# --------------------------------------------------------------------------- #

def _is_retryable(exc: BaseException) -> bool:
    # Excludes CancelledError/KeyboardInterrupt (BaseException) and permanent errors.
    return isinstance(exc, Exception) and not isinstance(exc, TaskNotFound)


def _log_retry(task_id: uuid.UUID, retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    # Only the exception class is logged: messages could embed PHI.
    logger.warning(
        "Task %s attempt %d/%d failed (%s); retrying with backoff",
        task_id, retry_state.attempt_number, MAX_ATTEMPTS, type(exc).__name__,
    )


async def _process_with_retries(
    redis: Redis, task_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=1, max=10),  # 1s, 2s, ...
            retry=retry_if_exception(_is_retryable),
            before_sleep=functools.partial(_log_retry, task_id),
            reraise=True,
        ):
            with attempt:
                await _run_attempt(task_id, payload)
    except TaskNotFound:
        logger.error("Task %s not found in DB; message discarded", task_id)
    except Exception as exc:
        await _fail_task(redis, task_id, payload, exc)


async def _run_attempt(task_id: uuid.UUID, payload: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as session:
        stmt = (
            update(TaskRecord)
            .where(TaskRecord.task_id == task_id)
            .values(status=TaskStatus.PROCESSING, attempts=TaskRecord.attempts + 1)
            .returning(TaskRecord.task_id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            raise TaskNotFound(str(task_id))
        await session.commit()

    result = await _simulate_ai(payload)

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(TaskRecord)
            .where(TaskRecord.task_id == task_id)
            .values(status=TaskStatus.COMPLETED, result=result)
        )
        await session.commit()
    logger.info("Task %s completed", task_id)


async def _simulate_ai(payload: dict[str, Any]) -> dict[str, Any]:
    """Stand-in for the AI interpretation engine (real integration: later milestone)."""
    if not settings.USE_MOCK_AI:
        raise NotImplementedError("Real AI engine is not implemented yet")
    if settings.ENVIRONMENT == "development" and payload.get("raw_data") == _FORCE_FAIL_MARKER:
        raise RuntimeError("Simulated AI failure")
    await asyncio.sleep(2)
    return {"mock": True, "summary": "Dummy interpretation result", "variants_analyzed": 0}


async def _fail_task(
    redis: Redis, task_id: uuid.UUID, payload: dict[str, Any], exc: Exception
) -> None:
    error_name = type(exc).__name__
    logger.error("Task %s failed after %d attempts (%s)", task_id, MAX_ATTEMPTS, error_name)

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(TaskRecord)
                .where(TaskRecord.task_id == task_id)
                .values(
                    status=TaskStatus.FAILED,
                    result={"error": f"Processing failed after {MAX_ATTEMPTS} attempts"},
                )
            )
            await session.commit()
    except Exception as db_exc:
        logger.error("Could not mark task %s as failed (%s)", task_id, type(db_exc).__name__)

    await _push_dlq(
        redis,
        {
            "task_id": str(task_id),
            "payload": payload,  # PHI: treat the DLQ with the same controls as the queue
            "error": error_name,
            "attempts": MAX_ATTEMPTS,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _push_dlq(redis: Redis, entry: dict[str, Any]) -> None:
    try:
        await redis.lpush(DEAD_LETTER_QUEUE, json.dumps(entry))
    except RedisError as exc:
        logger.error("Could not push to dead letter queue (%s)", type(exc).__name__)