"""
In-memory sliding-window rate limiter for the ARI API.
60 requests per minute per key (or per IP when auth is disabled).
Auth endpoints use a tighter 5 requests per minute per IP limit.
"""

import os
import time
from collections import defaultdict

from quart import Response, jsonify, request

RATE_LIMIT = 60
WINDOW_SECONDS = 60

AUTH_RATE_LIMIT = 5
AUTH_WINDOW_SECONDS = 60

# Auth endpoints that need tighter per-IP rate limiting
_AUTH_RATE_LIMIT_PATHS = frozenset({
    "/auth/magic-link/send",
    "/auth/magic-link/verify",
    "/auth/exchange",
})


def _get_identifier() -> str:
    """
    Return a stable identifier for rate limiting, in priority order:
    1. Authenticated user_id (set by JWT middleware) — per-user limiting
    2. API key — per-key limiting for server-to-server clients
    3. Client IP — last resort for unauthenticated paths
    """
    # JWT-authenticated user
    user_id = getattr(request, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # API key (server-to-server)
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
    def __init__(self, limit: int = RATE_LIMIT, window: int = WINDOW_SECONDS) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._limit = limit
        self._window = window

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self._window
        timestamps = self._requests[key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        self._prune(key, now)
        timestamps = self._requests[key]

        if len(timestamps) >= self._limit:
            retry_after = int(timestamps[0] + self._window - now) + 1
            return False, max(retry_after, 1)

        timestamps.append(now)
        return True, 0


_limiter = SlidingWindowRateLimiter(limit=RATE_LIMIT, window=WINDOW_SECONDS)
_auth_limiter = SlidingWindowRateLimiter(limit=AUTH_RATE_LIMIT, window=AUTH_WINDOW_SECONDS)

SKIP_RATE_LIMIT_PATHS = frozenset({"/", "/health", "/webhook/stripe"})


def _get_client_ip() -> str:
    """Return the real client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "")


async def rate_limit_middleware() -> Response | None:
    """Before-request hook. Returns 429 when rate limit exceeded, None otherwise."""
    if request.path in SKIP_RATE_LIMIT_PATHS:
        return None

    if request.method == "OPTIONS":
        return None

    # Tighter auth-specific rate limit (5/min per IP)
    if request.path in _AUTH_RATE_LIMIT_PATHS:
        ip = _get_client_ip()
        allowed, retry_after = _auth_limiter.check(f"auth:{ip}")
        if not allowed:
            return jsonify({
                "error": "Too many authentication attempts. Please try again later.",
                "retry_after": retry_after,
            }), 429

    identifier = _get_identifier()
    allowed, retry_after = _limiter.check(identifier)

    if not allowed:
        return jsonify({
            "error": "Rate limit exceeded",
            "retry_after": retry_after,
        }), 429

    return None
