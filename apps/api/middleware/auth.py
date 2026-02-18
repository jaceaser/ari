"""
Authentication middleware for the ARI API.

Two auth schemes coexist:
- API key auth: for /v1/* endpoints (legacy backward compat)
- JWT auth: for /sessions/*, /lead-runs/*, /auth/* endpoints (Phase 2)
"""

import logging
import os

from quart import Response, jsonify, request

logger = logging.getLogger("api.auth")

SKIP_AUTH_PATHS = frozenset({"/", "/health", "/webhook/stripe"})

# ── API Key Auth (existing) ──


def _get_allowed_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "").strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


def _extract_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


async def auth_middleware() -> Response | None:
    """Before-request hook for API key auth. Returns 401 Response on failure, or None."""
    allowed_keys = _get_allowed_keys()
    if not allowed_keys:
        return None

    if request.path in SKIP_AUTH_PATHS:
        return None

    if request.method == "OPTIONS":
        return None

    token = _extract_bearer_token()
    if not token or token not in allowed_keys:
        return jsonify({"error": "Unauthorized"}), 401

    return None


# ── JWT Auth (Phase 2) ──

_JWT_SECRET: str | None = None
_JWT_ALGORITHM: str = "HS256"


def _get_jwt_config() -> tuple[str, str]:
    global _JWT_SECRET, _JWT_ALGORITHM
    if _JWT_SECRET is None:
        _JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
        _JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
    return _JWT_SECRET, _JWT_ALGORITHM


async def jwt_auth_middleware() -> Response | None:
    """Before-request hook for JWT auth. Sets request.user_id and request.user_email."""
    if request.path in SKIP_AUTH_PATHS or request.method == "OPTIONS":
        return None

    # Public auth endpoints — no JWT required
    if request.path == "/auth/exchange":
        return None
    if request.path.startswith("/auth/magic-link/"):
        return None

    secret, algorithm = _get_jwt_config()
    if not secret:
        # JWT not configured — allow through for local dev (like API key auth pattern)
        logger.warning("JWT_SECRET not set; JWT auth disabled.")
        return None

    try:
        import jwt as pyjwt
    except ImportError:
        logger.error("PyJWT not installed; cannot verify JWT.")
        return jsonify({"error": "Server configuration error"}), 500

    token = _extract_bearer_token()
    if not token:
        return jsonify({"error": "Unauthorized", "detail": "Missing bearer token"}), 401

    try:
        payload = pyjwt.decode(token, secret, algorithms=[algorithm])
    except pyjwt.ExpiredSignatureError:
        return jsonify({"error": "Unauthorized", "detail": "Token expired"}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"error": "Unauthorized", "detail": "Invalid token"}), 401

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id:
        return jsonify({"error": "Unauthorized", "detail": "Missing sub claim"}), 401

    request.user_id = user_id  # type: ignore[attr-defined]
    request.user_email = email  # type: ignore[attr-defined]
    return None
