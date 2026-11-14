import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api.endpoints import router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limiter import RateLimitMiddleware
from app.core.redis_client import close_redis, init_redis
from app.core.telemetry import (
    RequestObservabilityMiddleware,
    setup_telemetry,
    shutdown_telemetry,
)
from app.db.session import engine, init_db
from app.workers.task_worker import SHUTDOWN_GRACE_SECONDS, run_worker

logger = get_logger("app.main")


def _log_worker_exit(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.critical("worker_crashed", error_class=type(exc).__name__, status="failed")


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
            logger.warning("worker_shutdown_timeout", status="cancelled", error_class="TimeoutError")
        await close_redis()
        await engine.dispose()
        shutdown_telemetry()


def create_app() -> FastAPI:
    """Application factory."""
    configure_logging()
    setup_telemetry(settings.ENVIRONMENT, settings.OTEL_EXPORTER_OTLP_ENDPOINT)

    app = FastAPI(
        title="GenomIQ LIS API",
        version="1.0.0",
        description="API for genetic data interpretation",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Starlette makes the LAST added middleware the outermost. CORS goes last
    # so that 429 responses from the rate limiter also carry CORS headers.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
            "X-Request-ID",
        ],
    )

    app.include_router(router)
    FastAPIInstrumentor.instrument_app(app)
    return app


app: FastAPI = create_app()
