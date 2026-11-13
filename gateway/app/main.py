import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router
from app.core.config import settings
from app.core.redis_client import RateLimitMiddleware, close_redis, init_redis
from app.db.session import engine, init_db
from app.workers.task_worker import SHUTDOWN_GRACE_SECONDS, run_worker

logger = logging.getLogger(__name__)


def _log_worker_exit(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.critical("Worker task crashed (%s)", type(exc).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    await init_db()
    redis = await init_redis()
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(
        run_worker(redis, stop_event), name="genomic-queue-worker"
    )
    worker_task.add_done_callback(_log_worker_exit)
    app.state.worker_task = worker_task

    try:
        yield
    finally:
        # Shutdown: stop consuming, drain in-flight jobs, then close connections.
        stop_event.set()
        try:
            await asyncio.wait_for(worker_task, timeout=SHUTDOWN_GRACE_SECONDS + 5)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Worker did not stop in time and was cancelled")
        await close_redis()
        await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="GenomIQ LIS API",
        version="1.0.0",
        description="API for genetic data interpretation",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Starlette makes the LAST added middleware the outermost. CORS goes last
    # so that 429 responses from the rate limiter also carry CORS headers.
    # app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app: FastAPI = create_app()