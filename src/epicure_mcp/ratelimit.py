"""In-process per-IP token-bucket rate limiter (best-effort).

Production currently runs one MCP container behind Cloudflare, where an
additional edge rule limits abusive request bursts before they reach origin.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


@dataclass
class Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    """Refill rate = ``per_minute / 60`` tokens/second, capped at ``burst``."""

    def __init__(self, per_minute: int = 60, burst: int = 10) -> None:
        self.refill_rate = per_minute / 60.0
        self.capacity = float(max(burst, 1))
        self._buckets: dict[str, Bucket] = defaultdict(self._fresh)
        self._lock = threading.Lock()

    def _fresh(self) -> Bucket:
        return Bucket(tokens=self.capacity, last_refill=time.monotonic())

    def consume(self, key: str, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_rate)
            bucket.last_refill = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True, 0.0
            missing = cost - bucket.tokens
            wait = missing / self.refill_rate if self.refill_rate > 0 else 60.0
            return False, wait


def client_ip(request: Request) -> str:
    cloudflare_ip = request.headers.get("cf-connecting-ip")
    if cloudflare_ip:
        return cloudflare_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a token-bucket limit on every request except `/healthz`."""

    def __init__(
        self,
        app: ASGIApp,
        per_minute: int = 60,
        burst: int = 10,
        exempt_paths: tuple[str, ...] = ("/healthz",),
    ) -> None:
        super().__init__(app)
        self.limiter = TokenBucketLimiter(per_minute=per_minute, burst=burst)
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        key = client_ip(request)
        ok, wait = self.limiter.consume(key)
        if not ok:
            return JSONResponse(
                {"error": "rate_limited", "retry_after_seconds": round(wait, 2)},
                status_code=429,
                headers={"Retry-After": str(max(1, int(wait + 1)))},
            )
        response: Response = await call_next(request)
        return response
