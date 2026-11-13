import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis, FakeServer
from fastapi import FastAPI
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import DEFAULT_RATE_LIMIT_KEY, RateLimitRule, Settings
from app.core.rate_limiter import RateLimitMiddleware, RedisProvider

LAB_A = "test-key-lab-a"  # capacity 5
LAB_B = "test-key-lab-b"  # capacity 2
REFILL_KEY = "test-key-refill"  # capacity 2, refills 1 token/s

# Near-zero refill rates make the tests deterministic (no tokens appear mid-test).
LIMITS = {
    LAB_A: RateLimitRule(capacity=5, refill_rate=0.001),
    LAB_B: RateLimitRule(capacity=2, refill_rate=0.001),
    REFILL_KEY: RateLimitRule(capacity=2, refill_rate=1.0),
    DEFAULT_RATE_LIMIT_KEY: RateLimitRule(capacity=3, refill_rate=0.001),
}


def build_app(provider: RedisProvider) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, rate_limits=LIMITS, redis_provider=provider)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"pong": True}

    return app


def make_client(app: FastAPI, ip: str = "127.0.0.1") -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 50000))
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[FakeAsyncRedis]:
    # Own FakeServer per test: fakeredis otherwise shares state per host:port.
    client = FakeAsyncRedis(server=FakeServer(), decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def app(redis: FakeAsyncRedis) -> FastAPI:
    async def provider() -> Redis:
        return redis

    return build_app(provider)


async def _only_bucket_key(redis: FakeAsyncRedis) -> str:
    keys = await redis.keys("ratelimit:*")
    assert len(keys) == 1
    return keys[0]


# --------------------------------------------------------------------------- #

def test_default_config_matches_spec() -> None:
    limits = Settings(_env_file=None).RATE_LIMITS
    assert limits["api_key_lab_a"] == RateLimitRule(capacity=100, refill_rate=50.0)
    assert limits["api_key_lab_b"] == RateLimitRule(capacity=20, refill_rate=10.0)
    assert limits["default"] == RateLimitRule(capacity=10, refill_rate=5.0)


def test_middleware_requires_default_rule() -> None:
    with pytest.raises(ValueError):
        RateLimitMiddleware(FastAPI(), rate_limits={LAB_A: LIMITS[LAB_A]})


async def test_remaining_decreases_then_429(app: FastAPI) -> None:
    async with make_client(app) as client:
        headers = {"X-API-Key": LAB_A}

        for i in range(5):
            r = await client.get("/ping", headers=headers)
            assert r.status_code == 200
            assert r.headers["X-RateLimit-Limit"] == "5"
            assert r.headers["X-RateLimit-Remaining"] == str(4 - i)
            assert int(r.headers["X-RateLimit-Reset"]) > 0
            assert "Retry-After" not in r.headers

        r = await client.get("/ping", headers=headers)
        assert r.status_code == 429
        assert r.json() == {"detail": "Too Many Requests"}
        assert r.headers["X-RateLimit-Limit"] == "5"
        assert r.headers["X-RateLimit-Remaining"] == "0"
        assert int(r.headers["X-RateLimit-Reset"]) >= 1
        assert int(r.headers["Retry-After"]) >= 1


async def test_buckets_are_independent_per_api_key(app: FastAPI) -> None:
    async with make_client(app) as client:
        for _ in range(2):
            assert (await client.get("/ping", headers={"X-API-Key": LAB_B})).status_code == 200
        assert (await client.get("/ping", headers={"X-API-Key": LAB_B})).status_code == 429

        r = await client.get("/ping", headers={"X-API-Key": LAB_A})
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Remaining"] == "4"


async def test_without_api_key_uses_default_limits_per_ip(app: FastAPI) -> None:
    async with make_client(app, ip="10.0.0.1") as client_1, make_client(
        app, ip="10.0.0.2"
    ) as client_2:
        for i in range(3):
            r = await client_1.get("/ping")
            assert r.status_code == 200
            assert r.headers["X-RateLimit-Limit"] == "3"
            assert r.headers["X-RateLimit-Remaining"] == str(2 - i)
        assert (await client_1.get("/ping")).status_code == 429

        # A different IP has its own bucket.
        assert (await client_2.get("/ping")).status_code == 200


async def test_unknown_api_keys_cannot_bypass_the_limit(app: FastAPI) -> None:
    async with make_client(app) as client:
        statuses = [
            (await client.get("/ping", headers={"X-API-Key": f"made-up-{i}"})).status_code
            for i in range(4)
        ]
    assert statuses == [200, 200, 200, 429]


async def test_health_is_exempt(app: FastAPI) -> None:
    async with make_client(app) as client:
        for _ in range(10):
            r = await client.get("/health")
            assert r.status_code == 200
            assert "X-RateLimit-Limit" not in r.headers

        # /health consumed nothing: the first real request still sees a full bucket.
        r = await client.get("/ping")
        assert r.headers["X-RateLimit-Remaining"] == "2"


async def test_concurrent_requests_are_atomic(app: FastAPI) -> None:
    async with make_client(app) as client:
        responses = await asyncio.gather(
            *[client.get("/ping", headers={"X-API-Key": LAB_A}) for _ in range(10)]
        )
    codes = sorted(r.status_code for r in responses)
    assert codes == [200] * 5 + [429] * 5


async def test_tokens_refill_over_time(app: FastAPI, redis: FakeAsyncRedis) -> None:
    headers = {"X-API-Key": REFILL_KEY}
    async with make_client(app) as client:
        assert (await client.get("/ping", headers=headers)).status_code == 200
        assert (await client.get("/ping", headers=headers)).status_code == 200
        assert (await client.get("/ping", headers=headers)).status_code == 429

        # Move last_refill 1.5s into the past instead of sleeping (deterministic).
        key = await _only_bucket_key(redis)
        last_refill = float(await redis.hget(key, "last_refill"))
        await redis.hset(key, "last_refill", f"{last_refill - 1.5:.6f}")

        r = await client.get("/ping", headers=headers)
        assert r.status_code == 200  # ~1.5 tokens were available
        assert r.headers["X-RateLimit-Remaining"] == "0"  # ~0.5 left
        assert (await client.get("/ping", headers=headers)).status_code == 429


async def test_raw_api_key_is_not_stored_in_redis(app: FastAPI, redis: FakeAsyncRedis) -> None:
    async with make_client(app) as client:
        await client.get("/ping", headers={"X-API-Key": LAB_A})

    key = await _only_bucket_key(redis)
    assert LAB_A not in key
    assert await redis.pttl(key) > 0  # idle buckets expire


async def test_fails_open_when_redis_is_down() -> None:
    async def broken_provider() -> Redis:
        raise RedisConnectionError("redis down")

    async with make_client(build_app(broken_provider)) as client:
        r = await client.get("/ping")
    assert r.status_code == 200
    assert "X-RateLimit-Limit" not in r.headers
