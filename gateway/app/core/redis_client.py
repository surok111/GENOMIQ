import logging
import math

from redis.asyncio import Redis
from redis.commands.core import AsyncScript
from redis.exceptions import RedisError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger(__name__)

# Queue names are shared by the API (producer) and the worker (consumer).
GENOMIC_QUEUE = "genomic_queue"
DEAD_LETTER_QUEUE = "dead_letter_queue"

RATE_LIMIT_MAX_TOKENS = 100
RATE_LIMIT_REFILL_RATE = 50.0  # tokens per second

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
    """FastAPI dependency (async, so it never hits the threadpool)."""
    if _redis is None:
        raise RuntimeError("Redis client is not initialised")
    return _redis


# --------------------------------------------------------------------------- #
# Token bucket rate limiter
# --------------------------------------------------------------------------- #

# Atomic refill + consume. Uses Redis server time (TIME) so app-server clock
# skew cannot affect the bucket. Floats are returned as strings because Redis
# truncates Lua numbers to integers.
_TOKEN_BUCKET_LUA = """
local key         = KEYS[1]
local max_tokens  = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested   = tonumber(ARGV[3])

local t   = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local data   = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts     = tonumber(data[2])
if tokens == nil or ts == nil then
  tokens = max_tokens
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

local allowed = 0
local retry_after = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  retry_after = (requested - tokens) / refill_rate
end

redis.call('HSET', key, 'tokens', tostring(tokens), 'ts', tostring(now))
redis.call('PEXPIRE', key, math.ceil(max_tokens / refill_rate * 1000) * 2)

return {allowed, tostring(retry_after)}
"""


class TokenBucketRateLimiter:
    def __init__(self, max_tokens: int, refill_rate: float) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._script: AsyncScript | None = None

    async def acquire(self, redis: Redis, identifier: str) -> tuple[bool, float]:
        """Try to take one token. Returns (allowed, retry_after_seconds)."""
        if self._script is None:
            self._script = redis.register_script(_TOKEN_BUCKET_LUA)
        allowed, retry_after = await self._script(
            keys=[f"ratelimit:{identifier}"],
            args=[self.max_tokens, self.refill_rate, 1],
            client=redis,
        )
        return int(allowed) == 1, float(retry_after)


class RateLimitMiddleware:
    """Pure ASGI middleware: per-client token bucket, 429 + Retry-After when empty."""

    def __init__(
        self,
        app: ASGIApp,
        limiter: TokenBucketRateLimiter | None = None,
        exempt_paths: frozenset[str] = frozenset({"/health"}),
    ) -> None:
        self.app = app
        self.limiter = limiter or TokenBucketRateLimiter(
            RATE_LIMIT_MAX_TOKENS, RATE_LIMIT_REFILL_RATE
        )
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        identifier = client[0] if client else "unknown"  # never logged

        try:
            allowed, retry_after = await self.limiter.acquire(
                await get_redis(), identifier
            )
        except (RedisError, RuntimeError) as exc:
            # Fail open: a Redis outage must not take the whole API down.
            logger.warning("Rate limiter unavailable (%s); allowing request", type(exc).__name__)
            await self.app(scope, receive, send)
            return

        if not allowed:
            response = JSONResponse(
                {"detail": "Too Many Requests"},
                status_code=429,
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)