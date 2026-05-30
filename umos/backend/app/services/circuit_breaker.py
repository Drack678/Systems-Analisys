import json
import time
from enum import Enum
from typing import Any, Callable, Awaitable

from app.core.redis_client import get_redis


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker con fallback Redis (TTL 60s) — R1 W3."""

    def __init__(
        self,
        upstream: str,
        threshold: int = 2,
        timeout_sec: int = 60,
        cache_ttl: int = 60,
    ):
        self.upstream = upstream
        self.threshold = threshold
        self.timeout_sec = timeout_sec
        self.cache_ttl = cache_ttl

    def _state_key(self) -> str:
        return f"cb:{self.upstream}:state"

    def _failures_key(self) -> str:
        return f"cb:{self.upstream}:failures"

    def _opened_at_key(self) -> str:
        return f"cb:{self.upstream}:opened_at"

    def _cache_key(self) -> str:
        return f"cb:{self.upstream}:cache"

    async def get_state(self) -> CircuitState:
        try:
            redis = await get_redis()
        except Exception:
            return CircuitState.CLOSED
        raw = await redis.get(self._state_key())
        if raw == CircuitState.OPEN.value:
            opened = float(await redis.get(self._opened_at_key()) or 0)
            if time.time() - opened >= self.timeout_sec:
                await redis.set(self._state_key(), CircuitState.HALF_OPEN.value)
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        if raw == CircuitState.HALF_OPEN.value:
            return CircuitState.HALF_OPEN
        return CircuitState.CLOSED

    async def record_success(self):
        redis = await get_redis()
        await redis.set(self._state_key(), CircuitState.CLOSED.value)
        await redis.set(self._failures_key(), 0)

    async def record_failure(self):
        redis = await get_redis()
        failures = int(await redis.incr(self._failures_key()))
        if failures >= self.threshold:
            await redis.set(self._state_key(), CircuitState.OPEN.value)
            await redis.set(self._opened_at_key(), time.time())

    async def get_cached(self) -> tuple[Any | None, int | None]:
        """Retorna (data, age_seconds)."""
        redis = await get_redis()
        raw = await redis.get(self._cache_key())
        if not raw:
            return None, None
        payload = json.loads(raw)
        age = int(time.time() - payload.get("ts", time.time()))
        return payload.get("data"), age

    async def set_cache(self, data: Any):
        redis = await get_redis()
        await redis.setex(
            self._cache_key(),
            self.cache_ttl,
            json.dumps({"ts": time.time(), "data": data}),
        )

    async def call(
        self,
        fetch_fn: Callable[[], Awaitable[Any]],
        fallback_fn: Callable[[], Any] | None = None,
    ) -> dict:
        """
        Ejecuta fetch con circuit breaker.
        Retorna { data, source, age_seconds, stale, circuit_state }.
        """
        state = await self.get_state()

        if state == CircuitState.OPEN:
            cached, age = await self.get_cached()
            if cached is not None:
                stale = (age or 0) > self.cache_ttl
                return {
                    "data": cached,
                    "source": "redis_cache",
                    "age_seconds": age,
                    "stale": stale,
                    "circuit_state": state.value,
                }
            if fallback_fn:
                return {
                    "data": fallback_fn(),
                    "source": "static_fallback",
                    "age_seconds": None,
                    "stale": True,
                    "circuit_state": state.value,
                }
            raise ConnectionError(f"Circuit open for {self.upstream}")

        try:
            data = await fetch_fn()
            await self.set_cache(data)
            await self.record_success()
            return {
                "data": data,
                "source": "live",
                "age_seconds": 0,
                "stale": False,
                "circuit_state": CircuitState.CLOSED.value,
            }
        except Exception:
            await self.record_failure()
            cached, age = await self.get_cached()
            if cached is not None:
                return {
                    "data": cached,
                    "source": "redis_cache",
                    "age_seconds": age,
                    "stale": (age or 0) > self.cache_ttl,
                    "circuit_state": (await self.get_state()).value,
                }
            if fallback_fn:
                return {
                    "data": fallback_fn(),
                    "source": "static_fallback",
                    "age_seconds": None,
                    "stale": True,
                    "circuit_state": (await self.get_state()).value,
                }
            raise
