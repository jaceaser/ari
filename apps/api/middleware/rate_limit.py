"""
In-memory sliding-window rate limiter for the ARI API.
60 requests per minute per key (or per IP when auth is disabled).
"""

import os
import time
from collections import defaultdict

from quart import Response, jsonify, request

RATE_LIMIT = 60
WINDOW_SECONDS = 60


def _get_identifier() -> str:
    """Return the API key if auth is active, otherwise the client IP."""
    api_keys_set = os.getenv("API_KEYS", "").strip()
    if api_keys_set:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return f"key:{header[7:].strip()}"
    # Behind a reverse proxy, use X-Forwarded-For for the real client IP
    forwarded = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
    return f"ip:{client_ip}"


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        timestamps = self._requests[key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        self._prune(key, now)
        timestamps = self._requests[key]

        if len(timestamps) >= RATE_LIMIT:
            retry_after = int(timestamps[0] + WINDOW_SECONDS - now) + 1
            return False, max(retry_after, 1)

        timestamps.append(now)
        return True, 0


_limiter = SlidingWindowRateLimiter()

SKIP_RATE_LIMIT_PATHS = frozenset({"/", "/health"})


async def rate_limit_middleware() -> Response | None:
    """Before-request hook. Returns 429 when rate limit exceeded, None otherwise."""
    if request.path in SKIP_RATE_LIMIT_PATHS:
        return None

    if request.method == "OPTIONS":
        return None

    identifier = _get_identifier()
    allowed, retry_after = _limiter.check(identifier)

    if not allowed:
        return jsonify({
            "error": "Rate limit exceeded",
            "retry_after": retry_after,
        }), 429

    return None
