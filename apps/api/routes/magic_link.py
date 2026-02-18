"""Magic link authentication endpoints.

POST /auth/magic-link/send  — send a magic link email
POST /auth/magic-link/verify — verify token and return JWT
"""

import datetime
import json
import logging
import os
import secrets
import ssl
import uuid

from quart import Blueprint, jsonify, request

logger = logging.getLogger("api.auth.magic_link")

magic_link_bp = Blueprint("magic_link", __name__)

# Simple in-memory rate limit: email -> last send timestamp
_send_timestamps: dict[str, float] = {}
_SEND_COOLDOWN_SECONDS = 60


async def _migrate_redis_subscription(email: str, user_id: str, cosmos) -> None:
    """On-login migration: check legacy Redis for subscription data and copy to Cosmos.

    This is a best-effort operation — if Redis is unavailable or the user has
    no subscription there, we silently skip. Once the one-time bulk migration
    script has been run this becomes a no-op for most users.
    """
    # Check if user already has subscription data in Cosmos
    existing = await cosmos.get_user_subscription(user_id)
    if existing and existing.get("subscription_status"):
        return  # Already migrated

    redis_host = os.getenv("REDIS_HOST", "").strip()
    redis_password = os.getenv("REDIS_PASSWORD", "").strip()
    if not redis_host or not redis_password:
        return  # Redis not configured, skip

    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.debug("redis package not installed; skipping on-login migration")
        return

    try:
        redis_port = int(os.getenv("REDIS_PORT", "6380"))
        client = aioredis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            ssl=True,
            ssl_cert_reqs=ssl.CERT_NONE,
            ssl_check_hostname=False,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            db=0,
        )

        raw = await client.get(f"subscription:{email}")
        await client.aclose()

        if not raw:
            return

        data = json.loads(raw)
        status = data.get("status", "")
        active_statuses = {"active", "pending", "trialing"}

        stripe_data = {
            "subscription_status": "active" if status in active_statuses else status,
            "subscription_id": data.get("subscription_id"),
            "plan": data.get("plan_type"),
            "subscription_expires_at": data.get("next_payment"),
            "legacy_redis_migrated": True,
        }

        await cosmos.update_user_subscription(user_id, stripe_data)
        logger.info("On-login migration: copied subscription for %s from Redis", email)

    except Exception:
        logger.debug("On-login Redis migration failed for %s (non-fatal)", email, exc_info=True)


def _get_frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")


def _get_jwt_config() -> tuple[str, str]:
    secret = os.getenv("JWT_SECRET", "").strip()
    algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip()
    return secret, algorithm


async def _send_email(email: str, link: str) -> None:
    """Send magic link email via Azure Communication Services."""
    endpoint = os.getenv("AZURE_COMMUNICATION_ENDPOINT", "").strip()
    if not endpoint:
        logger.warning("AZURE_COMMUNICATION_ENDPOINT not set; logging link instead")
        logger.info("Magic link for %s: %s", email, link)
        return

    try:
        from azure.communication.email import EmailClient
    except ImportError:
        logger.error("azure-communication-email not installed; cannot send email")
        logger.info("Magic link for %s: %s", email, link)
        return

    sender = os.getenv(
        "AZURE_COMMUNICATION_SENDER",
        "DoNotReply@reilabs.ai",
    )

    client = EmailClient.from_connection_string(endpoint)
    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": email}]},
        "content": {
            "subject": "Sign in to ARI",
            "plainText": f"Click this link to sign in:\n\n{link}\n\nThis link expires in 15 minutes.",
            "html": (
                "<p>Click the link below to sign in to ARI:</p>"
                f'<p><a href="{link}">Sign in to ARI</a></p>'
                "<p>This link expires in 15 minutes. If you didn't request this, ignore this email.</p>"
            ),
        },
    }

    try:
        poller = client.begin_send(message)
        poller.result()
        logger.info("Magic link email sent to %s", email)
    except Exception:
        logger.exception("Failed to send magic link email to %s", email)
        raise


@magic_link_bp.post("/auth/magic-link/send")
async def send_magic_link():
    """Generate a magic token, store in Cosmos, and email the link."""
    body = await request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    # Rate limit: 1 email per address per 60 seconds
    import time

    now = time.time()
    last_sent = _send_timestamps.get(email, 0)
    if now - last_sent < _SEND_COOLDOWN_SECONDS:
        retry_after = int(_SEND_COOLDOWN_SECONDS - (now - last_sent)) + 1
        return jsonify({
            "error": "Too many requests",
            "detail": f"Please wait {retry_after} seconds before requesting another link",
            "retry_after": retry_after,
        }), 429

    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=15)
    ).isoformat()

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if cosmos:
        await cosmos.store_magic_token(email, token, expires_at)
    else:
        logger.error("Cosmos DB not configured; cannot store magic token")
        return jsonify({"error": "Server configuration error"}), 500

    frontend_url = _get_frontend_url()
    link = f"{frontend_url}/verify?token={token}"

    try:
        await _send_email(email, link)
    except Exception:
        # Clean up token on email failure
        await cosmos.delete_magic_token(token)
        return jsonify({"error": "Failed to send email"}), 500

    _send_timestamps[email] = now

    return jsonify({"ok": True})


@magic_link_bp.post("/auth/update-email")
async def update_email():
    """Update the authenticated user's email. Sends a magic link to verify the new address."""
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json(silent=True) or {}
    new_email = (body.get("email") or "").strip().lower()

    if not new_email or "@" not in new_email:
        return jsonify({"error": "Valid email is required"}), 400

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Server configuration error"}), 500

    # Check if the new email is already in use by another user
    existing = await cosmos.find_user_by_email(new_email)
    if existing and existing.get("userId") != user_id:
        return jsonify({"error": "Email already in use"}), 409

    # Update the user document directly
    await cosmos.update_user_email(user_id, new_email)

    return jsonify({"ok": True, "email": new_email})


@magic_link_bp.post("/auth/magic-link/verify")
async def verify_magic_link():
    """Verify a magic token and return a JWT."""
    body = await request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()

    if not token:
        return jsonify({"error": "Token is required"}), 400

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Server configuration error"}), 500

    doc = await cosmos.verify_magic_token(token)
    if not doc:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Single-use: delete immediately
    await cosmos.delete_magic_token(token)

    email = doc["email"]

    # Check if user already exists with this email (handles email changes).
    # If they changed their email, the user doc has the new email but the old user_id.
    # Using find_user_by_email ensures we reuse the existing account.
    existing = await cosmos.find_user_by_email(email)
    if existing:
        user_id = existing.get("userId", existing.get("id"))
    else:
        # Derive deterministic user ID for new users
        user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))

    # Ensure user exists in Cosmos
    await cosmos.ensure_user(user_id, email)

    # Migrate subscription data from legacy Redis if not already in Cosmos
    await _migrate_redis_subscription(email, user_id, cosmos)

    # Issue JWT
    secret, algorithm = _get_jwt_config()
    if not secret:
        return jsonify({"error": "Server configuration error", "detail": "JWT_SECRET not set"}), 500

    try:
        import jwt as pyjwt
    except ImportError:
        return jsonify({"error": "Server configuration error"}), 500

    now = datetime.datetime.now(datetime.timezone.utc)
    jwt_payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=24),
    }

    jwt_token = pyjwt.encode(jwt_payload, secret, algorithm=algorithm)

    return jsonify({
        "token": jwt_token,
        "user": {"id": user_id, "email": email},
    })
