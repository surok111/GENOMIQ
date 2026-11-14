import asyncio
import functools
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace
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

from app.core.logging import get_logger
from app.core.redis_client import DEAD_LETTER_QUEUE, GENOMIC_QUEUE
from app.core.telemetry import (
    extract_trace_context,
    fhir_validation_failures,
    get_tracer,
    mark_span_error,
)
from app.db.models import TaskRecord, TaskStatus
from app.db.session import AsyncSessionLocal
from app.services.dependencies import get_ai_service
from app.services.fhir_mapper import build_fhir_bundle

logger = get_logger("app.workers.task_worker")

MAX_CONCURRENCY = 5
MAX_ATTEMPTS = 3
BRPOP_TIMEOUT_SECONDS = 1  # short, so the loop notices the stop event quickly
SHUTDOWN_GRACE_SECONDS = 15
RETRY_WAIT = wait_exponential(multiplier=1, min=1, max=10)  # 1s, 2s, ... (patched in tests)


class TaskNotFound(Exception):
    """Queue message references a task that no longer exists in the DB."""


class PermanentTaskError(Exception):
    """A failure that retrying cannot fix (e.g. the AI engine rejected the input)."""


@dataclass(frozen=True)
class QueueJob:
    task_id: uuid.UUID
    payload: dict[str, Any]
    trace_context: dict[str, str]
    correlation_id: str | None


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
    logger.info("worker_started", status="running", concurrency=MAX_CONCURRENCY)

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
            logger.info("worker_draining", status="draining", in_flight=len(in_flight))
            _, pending = await asyncio.wait(in_flight, timeout=SHUTDOWN_GRACE_SECONDS)
            for job in pending:
                job.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        logger.info("worker_stopped", status="stopped")


async def _pop_job(redis: Redis) -> str | None:
    try:
        item = await redis.brpop([GENOMIC_QUEUE], timeout=BRPOP_TIMEOUT_SECONDS)
    except RedisError as exc:
        logger.error("brpop_failed", status="retrying", error_class=type(exc).__name__)
        await asyncio.sleep(1)
        return None
    return item[1] if item else None


async def _handle_job(redis: Redis, raw: str, semaphore: asyncio.Semaphore) -> None:
    try:
        try:
            job = _parse_message(raw)
        except ValueError:
            # Do not log `raw`: the queue body contains PHI.
            logger.error("malformed_queue_message", status="failed", error_class="ValueError")
            await _push_dlq(redis, {"error": "MalformedMessage"})
            return
        parent = extract_trace_context(job.trace_context)
        with get_tracer().start_as_current_span("worker.task", context=parent) as span:
            span.set_attribute("task_id", str(job.task_id))
            if job.correlation_id:
                span.set_attribute("correlation_id", job.correlation_id)
            await _process_with_retries(
                redis, job.task_id, job.payload, correlation_id=job.correlation_id
            )
    except Exception as exc:  # last line of defence; the loop must survive
        logger.error("worker_unhandled", status="failed", error_class=type(exc).__name__)
    finally:
        semaphore.release()


def _parse_message(raw: str) -> QueueJob:
    try:
        message = json.loads(raw)
        task_id = uuid.UUID(message["task_id"])
        payload = message["payload"]
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("malformed message") from exc
    if not isinstance(payload, dict):
        raise ValueError("malformed message")
    trace_context = _string_map(message.get("trace_context"))
    correlation_id = message.get("correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id.strip():
        correlation_id = None
    else:
        correlation_id = correlation_id.strip()[:64]
    return QueueJob(
        task_id=task_id,
        payload=payload,
        trace_context=trace_context,
        correlation_id=correlation_id,
    )


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


# --------------------------------------------------------------------------- #
# Processing, retries, DLQ
# --------------------------------------------------------------------------- #

def _is_retryable(exc: BaseException) -> bool:
    # Excludes CancelledError/KeyboardInterrupt (BaseException) and permanent errors.
    return isinstance(exc, Exception) and not isinstance(
        exc, (TaskNotFound, PermanentTaskError, NotImplementedError)
    )


def _log_retry(task_id: uuid.UUID, retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    # Only the exception class is logged: messages could embed PHI.
    logger.warning(
        "task_retry",
        task_id=str(task_id),
        status="retrying",
        error_class=type(exc).__name__ if exc else None,
        attempt=retry_state.attempt_number,
    )


async def _process_with_retries(
    redis: Redis,
    task_id: uuid.UUID,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    attempts_made = 0
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=RETRY_WAIT,
            retry=retry_if_exception(_is_retryable),
            before_sleep=functools.partial(_log_retry, task_id),
            reraise=True,
        ):
            with attempt:
                attempts_made += 1
                await _run_attempt(task_id, payload, correlation_id)
    except TaskNotFound:
        logger.error(
            "task_missing",
            task_id=str(task_id),
            correlation_id=correlation_id,
            status="discarded",
            error_class="TaskNotFound",
        )
    except Exception as exc:
        await _fail_task(redis, task_id, payload, exc, attempts_made, correlation_id)


async def _run_attempt(
    task_id: uuid.UUID, payload: dict[str, Any], correlation_id: str | None = None
) -> None:
    started = time.perf_counter()
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

    raw_data = payload.get("raw_data")
    if not isinstance(raw_data, str):
        raise PermanentTaskError("payload has no raw_data")

    ai_service = await get_ai_service()
    tracer = get_tracer()
    with tracer.start_as_current_span("worker.ai.inference") as span:
        _span_ids(span, task_id, correlation_id)
        try:
            result = await ai_service.interpret(raw_data)
        except ValueError as exc:
            # The AI engine rejected the input; retrying the same input can't help.
            mark_span_error(span, exc)
            raise PermanentTaskError("input could not be interpreted") from exc
        except Exception as exc:
            mark_span_error(span, exc)
            raise

    with tracer.start_as_current_span("worker.fhir.assemble") as span:
        _span_ids(span, task_id, correlation_id)
        try:
            fhir_bundle = build_fhir_bundle(result)
        except ValueError as exc:
            # The same AI payload will fail FHIR validation every time.
            mark_span_error(span, exc)
            fhir_validation_failures().add(1)
            raise PermanentTaskError("input could not be interpreted") from exc
        except Exception as exc:
            mark_span_error(span, exc)
            raise

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(TaskRecord)
            .where(TaskRecord.task_id == task_id)
            .values(status=TaskStatus.COMPLETED, result=fhir_bundle)
        )
        await session.commit()
    logger.info(
        "task_completed",
        task_id=str(task_id),
        correlation_id=correlation_id,
        status="completed",
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def _span_ids(span: trace.Span, task_id: uuid.UUID, correlation_id: str | None) -> None:
    span.set_attribute("task_id", str(task_id))
    if correlation_id:
        span.set_attribute("correlation_id", correlation_id)


async def _fail_task(
    redis: Redis,
    task_id: uuid.UUID,
    payload: dict[str, Any],
    exc: Exception,
    attempts: int,
    correlation_id: str | None = None,
) -> None:
    error_name = type(exc).__name__
    logger.error(
        "task_failed",
        task_id=str(task_id),
        correlation_id=correlation_id,
        status="failed",
        error_class=error_name,
        attempts=attempts,
    )

    message = (
        "Input could not be interpreted"
        if isinstance(exc, PermanentTaskError)
        else f"Processing failed after {attempts} attempts"
    )
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(TaskRecord)
                .where(TaskRecord.task_id == task_id)
                .values(status=TaskStatus.FAILED, result={"error": message})
            )
            await session.commit()
    except Exception as db_exc:
        logger.error(
            "task_fail_persist_error",
            task_id=str(task_id),
            correlation_id=correlation_id,
            status="failed",
            error_class=type(db_exc).__name__,
        )

    await _push_dlq(
        redis,
        {
            "task_id": str(task_id),
            "payload": payload,  # PHI: treat the DLQ with the same controls as the queue
            "error": error_name,
            "attempts": attempts,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _push_dlq(redis: Redis, entry: dict[str, Any]) -> None:
    try:
        await redis.lpush(DEAD_LETTER_QUEUE, json.dumps(entry))
    except RedisError as exc:
        logger.error("dlq_push_failed", status="failed", error_class=type(exc).__name__)
