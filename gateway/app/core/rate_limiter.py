"""Per-tenant token bucket rate limiting (Redis + Lua)."""

import hashlib
import logging
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.commands.core import AsyncScript
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import DEFAULT_RATE_LIMIT_KEY, RateLimitRule, settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

RedisProvider = Callable[[], Awaitable[Redis]]

API_KEY_HEADER = "X-API-Key"
BUCKET_PREFIX = "ratelimit"

# Atomic refill + consume.
#  * Uses Redis server TIME, so clock skew between app instances is irrelevant.
#    (Needs Redis >= 5: TIME before a write inside a script is allowed there.)
#  * Lua numbers are truncated to integers in replies, so the fractional token
#    count and retry_after are returned as strings.
# Returns: {allowed (0|1), remaining_tokens (string), retry_after_seconds (string)}
TOKEN_BUCKET_LUA = """
local key         = KEYS[1]
local capacity    = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested   = tonumber(ARGV[3])

local t   = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local bucket      = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens      = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil or last_refill == nil then
  tokens = capacity
  last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
local retry_after = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  retry_after = (requested - tokens) / refill_rate
end

redis.call('HSET', key,
  'tokens', string.format('%.10f', tokens),
  'last_refill', string.format('%.6f', now))

-- An idle bucket is equivalent to a full one after capacity/refill_rate seconds,
-- so the state can safely expire (with a 1s margin).
redis.call('PEXPIRE', key, math.ceil(capacity / refill_rate * 1000) + 1000)

return {allowed, string.format('%.10f', tokens), string.format('%.6f', retry_after)}
"""


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int  # whole tokens left, for X-RateLimit-Remaining
    retry_after: float  # seconds until one token is available (0 when allowed)
    reset_after: float  # seconds until the bucket is completely full again


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket per API key (or per client IP), with X-RateLimit-* headers."""

    def __init__(
        self,
        app: ASGIApp,
        rate_limits: Mapping[str, RateLimitRule] | None = None,
        redis_provider: RedisProvider | None = None,
        exempt_paths: frozenset[str] = frozenset({"/health"}),
    ) -> None:
        super().__init__(app)
        self._rate_limits: dict[str, RateLimitRule] = dict(
            rate_limits if rate_limits is not None else settings.RATE_LIMITS
        )
        if DEFAULT_RATE_LIMIT_KEY not in self._rate_limits:
            raise ValueError(f'rate_limits must define a "{DEFAULT_RATE_LIMIT_KEY}" entry')
        self._get_redis: RedisProvider = redis_provider or get_redis
        self._exempt_paths = exempt_paths
        self._script: AsyncScript | None = None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        rule, bucket_key = self._resolve(request)

        decision: RateLimitDecision | None = None
        try:
            redis = await self._get_redis()
            decision = await self._consume(redis, bucket_key, rule)
        except (RedisError, RuntimeError) as exc:
            # Fail open: a Redis outage must not take the whole API down.
            # Only the exception class is logged (no keys, no IPs).
            logger.warning(
                "Rate limiter unavailable (%s); allowing request", type(exc).__name__
            )

        if decision is None:
            return await call_next(request)

        response: Response
        if decision.allowed:
            response = await call_next(request)
        else:
            response = JSONResponse({"detail": "Too Many Requests"}, status_code=429)
            response.headers["Retry-After"] = str(max(1, math.ceil(decision.retry_after)))

        response.headers["X-RateLimit-Limit"] = str(rule.capacity)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(math.ceil(decision.reset_after))
        return response

    def _resolve(self, request: Request) -> tuple[RateLimitRule, str]:
        """Pick the rule and the Redis bucket key for this request."""
        api_key = request.headers.get(API_KEY_HEADER)
        if api_key and api_key != DEFAULT_RATE_LIMIT_KEY and api_key in self._rate_limits:
            # Hash the key so raw API keys never appear in the Redis keyspace.
            digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            return self._rate_limits[api_key], f"{BUCKET_PREFIX}:key:{digest}"

        # No key, or a key we don't know: default limits, bucketed by client IP.
        # (Bucketing unknown keys by the key itself would let a caller get a
        # fresh bucket per made-up key.)
        client_ip = request.client.host if request.client else "unknown"
        return self._rate_limits[DEFAULT_RATE_LIMIT_KEY], f"{BUCKET_PREFIX}:ip:{client_ip}"

    async def _consume(
        self, redis: Redis, bucket_key: str, rule: RateLimitRule
    ) -> RateLimitDecision:
        if self._script is None:
            self._script = redis.register_script(TOKEN_BUCKET_LUA)
        allowed, tokens, retry_after = await self._script(
            keys=[bucket_key],
            args=[rule.capacity, rule.refill_rate, 1],
            client=redis,
        )
        tokens_left = float(tokens)
        return RateLimitDecision(
            allowed=int(allowed) == 1,
            remaining=max(0, math.floor(tokens_left)),
            retry_after=float(retry_after),
            reset_after=max(0.0, (rule.capacity - tokens_left) / rule.refill_rate),
        )
