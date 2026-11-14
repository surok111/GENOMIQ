import hashlib
import json
import uuid
from typing import Annotated, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.redis_client import GENOMIC_QUEUE, get_redis
from app.core.telemetry import correlation_id_from_request, get_tracer, inject_trace_context, mark_span_error
from app.db.models import TaskRecord, TaskStatus
from app.db.session import get_db
from app.schemas.genomic import GenomicReportAccepted, GenomicReportRequest
from app.schemas.task import TaskStatusResponse
from app.services.ai_interface import AIService
from app.services.dependencies import get_ai_service

logger = get_logger("app.api.endpoints")
router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
IdempotencyKeyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
        description="Client-generated key; retries with the same key never create duplicates.",
    ),
]


def _status_url(request: Request, task_id: uuid.UUID) -> str:
    return str(request.app.url_path_for("get_task_status", task_id=str(task_id)))


async def _get_by_idempotency_key(db: AsyncSession, key: str) -> TaskRecord | None:
    result = await db.execute(
        select(TaskRecord).where(TaskRecord.idempotency_key == key)
    )
    return result.scalar_one_or_none()


def _replay(
    existing: TaskRecord, fingerprint: str, request: Request, response: Response
) -> GenomicReportAccepted:
    """Answer a duplicate request with the original task's Location."""
    if existing.request_fingerprint != fingerprint:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key was already used with a different request payload",
        )
    response.headers["Location"] = _status_url(request, existing.task_id)
    response.headers["Idempotent-Replayed"] = "true"
    return GenomicReportAccepted()


@router.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.post(
    "/v1/genomic-interpretations",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenomicReportAccepted,
    tags=["Genomic Interpretations"],
)
async def create_genomic_interpretation(
    payload: GenomicReportRequest,
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
    ai_service: AIServiceDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> GenomicReportAccepted:
    """Accept a genomic report for asynchronous interpretation.

    The payload contains PHI and must never be logged.

    `ai_service` is injected so the DI wiring is exercised here, but it is
    intentionally NOT called: interpretation is the worker's job. Calling it
    inline would add ~1.5s to every request, run the AI twice per task, and
    turn an unreadable genotype into a 500 instead of a failed task.
    """
    correlation_id = correlation_id_from_request(request)
    response.headers["X-Request-ID"] = correlation_id
    tracer = get_tracer()
    with tracer.start_as_current_span("gateway.payload.validate") as span:
        span.set_attribute("correlation_id", correlation_id)
        try:
            # Hash only. The raw payload is not attached to the span or the log.
            fingerprint = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()
        except Exception as exc:
            mark_span_error(span, exc)
            raise

        # Fast path: duplicate request.
        if idempotency_key is not None:
            existing = await _get_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return _replay(existing, fingerprint, request, response)

        task_id = uuid.uuid4()
        span.set_attribute("task_id", str(task_id))
        record = TaskRecord(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            attempts=0,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            correlation_id=correlation_id,
        )
        db.add(record)
        try:
            await db.commit()
        except IntegrityError:
            # Lost a race against a concurrent request with the same key.
            await db.rollback()
            existing = (
                await _get_by_idempotency_key(db, idempotency_key)
                if idempotency_key is not None
                else None
            )
            if existing is None:
                raise
            return _replay(existing, fingerprint, request, response)

        # Captured while this span is current, so the worker continues the same trace.
        trace_context = inject_trace_context()
        # DB row is committed BEFORE the push, so the worker always finds it.
        message = json.dumps(
            {
                "task_id": str(task_id),
                "correlation_id": correlation_id,
                "trace_context": trace_context,
                "payload": payload.model_dump(mode="json"),
            }
        )
        try:
            await redis.lpush(GENOMIC_QUEUE, message)
        except RedisError as exc:
            mark_span_error(span, exc)
            logger.error(
                "enqueue_failed",
                task_id=str(task_id),
                correlation_id=correlation_id,
                status="failed",
                error_class=type(exc).__name__,
            )
            # Compensate so no orphan "queued" row exists and the key can be retried.
            await db.delete(record)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Queue unavailable, please retry",
            ) from None

    response.headers["Location"] = _status_url(request, task_id)
    response.headers["X-Request-ID"] = correlation_id
    logger.info(
        "task_accepted",
        task_id=str(task_id),
        correlation_id=correlation_id,
        status="queued",
    )
    return GenomicReportAccepted()


@router.get(
    "/v1/status/{task_id}",
    response_model=TaskStatusResponse,
    tags=["Genomic Interpretations"],
)
async def get_task_status(
    task_id: uuid.UUID, response: Response, db: DbSession
) -> TaskRecord:
    """Return the current status (and result, once available) of a task."""
    record = await db.get(TaskRecord, task_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    response.headers["Cache-Control"] = "no-store"  # results may become PHI later
    return record
