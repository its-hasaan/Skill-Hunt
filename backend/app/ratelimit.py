"""
In-process sliding-window rate limiting.

Render runs this API as a single instance and there is no Redis, so limits are
kept in memory rather than in a shared store. That means the counters reset on
deploy and would not be shared if the service were ever scaled to >1 instance —
at that point this should move to Redis.

Two tiers, both configurable from the environment:
  * expensive endpoints (resume parsing, extension analysis) — a low limit,
    because each request reads an upload and runs several queries;
  * everything else — the general per-IP limit.
"""

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60

# Path prefixes (after the API prefix) that get the expensive-tier limit.
EXPENSIVE_PREFIXES = ("/resume", "/extension")

# Never rate limit the health check — Render's health probe and the keep-warm
# workflow hit it every few minutes and must not be throttled.
EXEMPT_PATHS = ("/health",)


class SlidingWindowLimiter:
    """Per-key request timestamps within a rolling window."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        # Tracks the clock passed into check(), not time.monotonic() directly,
        # so pruning stays correct whatever time source the caller uses.
        self._last_prune: float | None = None

    def _prune(self, now: float) -> None:
        """Drop keys with no recent hits so idle clients don't leak memory."""
        cutoff = now - WINDOW_SECONDS
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]
        self._last_prune = now

    def check(self, key: str, limit: int, now: float) -> tuple[bool, int]:
        """Record a hit for `key`. Returns (allowed, retry_after_seconds)."""
        if self._last_prune is None:
            self._last_prune = now
        elif now - self._last_prune > WINDOW_SECONDS:
            self._prune(now)

        hits = self._hits[key]
        cutoff = now - WINDOW_SECONDS
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= limit:
            # Oldest hit in the window decides when a slot frees up.
            return False, max(1, int(hits[0] + WINDOW_SECONDS - now) + 1)

        hits.append(now)
        return True, 0


_limiter = SlidingWindowLimiter()


def _client_key(request: Request) -> str:
    """Identify the caller by IP.

    Render terminates TLS at its proxy, so request.client.host is the proxy.
    The left-most X-Forwarded-For entry is the original client.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit_for(path: str, api_prefix: str, general: int, expensive: int) -> int:
    if path.startswith(api_prefix):
        suffix = path[len(api_prefix):]
        if suffix.startswith(EXPENSIVE_PREFIXES):
            return expensive
    return general


async def rate_limit_middleware(request: Request, call_next):
    """Reject callers that exceed their per-minute budget with a 429."""
    from .config import get_settings

    settings = get_settings()
    path = request.url.path

    # Preflight carries no credentials and must not be throttled, or the
    # browser will report a CORS failure instead of a rate-limit error.
    if path in EXEMPT_PATHS or request.method == "OPTIONS":
        return await call_next(request)

    limit = _limit_for(
        path,
        settings.api_prefix,
        settings.rate_limit_per_minute,
        settings.rate_limit_expensive_per_minute,
    )
    key = f"{_client_key(request)}:{'exp' if limit == settings.rate_limit_expensive_per_minute else 'gen'}"

    allowed, retry_after = _limiter.check(key, limit, time.monotonic())
    if not allowed:
        logger.warning(f"Rate limit hit: {key} on {path}")
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "detail": f"Rate limit of {limit} requests per minute exceeded. "
                          f"Try again in {retry_after}s.",
            },
            headers={"Retry-After": str(retry_after)},
        )

    return await call_next(request)
