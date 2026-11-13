from redis.asyncio import Redis

from app.core.config import settings

# Queue names are shared by the API (producer) and the worker (consumer).
GENOMIC_QUEUE = "genomic_queue"
DEAD_LETTER_QUEUE = "dead_letter_queue"

_redis: Redis | None = None


async def init_redis() -> Redis:
    """Create the shared async Redis client and verify connectivity."""
    global _redis
    client = Redis.from_url(
        settings.REDIS_URL.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=5,
        health_check_interval=30,
        # No socket_timeout: BRPOP blocks server-side and must not trip a client timeout.
    )
    await client.ping()
    _redis = client
    return client


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_redis() -> Redis:
    """FastAPI dependency / middleware provider (async, never hits the threadpool)."""
    if _redis is None:
        raise RuntimeError("Redis client is not initialised")
    return _redis
