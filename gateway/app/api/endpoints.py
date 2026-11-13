import hashlib
import json
import logging
import uuid
from typing import Annotated, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import GENOMIC_QUEUE, get_redis
from app.db.models import TaskRecord, TaskStatus
from app.db.session import get_db
from app.schemas.genomic import GenomicReportAccepted, GenomicReportRequest
from app.schemas.task import TaskStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
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
    idempotency_key: IdempotencyKeyHeader = None,
) -> GenomicReportAccepted:
    """Accept a genomic report for asynchronous interpretation.

    The payload contains PHI and must never be logged.
    """
    fingerprint = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()

    # Fast path: duplicate request.
    if idempotency_key is not None:
        existing = await _get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return _replay(existing, fingerprint, request, response)

    task_id = uuid.uuid4()
    record = TaskRecord(
        task_id=task_id,
        status=TaskStatus.QUEUED,
        attempts=0,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
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

    # DB row is committed BEFORE the push, so the worker always finds it.
    message = json.dumps(
        {"task_id": str(task_id), "payload": payload.model_dump(mode="json")}
    )
    try:
        await redis.lpush(GENOMIC_QUEUE, message)
    except RedisError as exc:
        logger.error("Failed to enqueue task %s (%s)", task_id, type(exc).__name__)
        # Compensate so no orphan "queued" row exists and the key can be retried.
        await db.delete(record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue unavailable, please retry",
        ) from None

    response.headers["Location"] = _status_url(request, task_id)
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