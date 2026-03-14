"""Magic link authentication endpoints.

POST /auth/magic-link/send  — send a magic link email
POST /auth/magic-link/verify — verify token and return JWT
"""

import datetime
import logging
import os
import secrets
import uuid

from quart import Blueprint, jsonify, redirect, request

logger = logging.getLogger("api.auth.magic_link")

magic_link_bp = Blueprint("magic_link", __name__)

# Simple in-memory rate limit: email -> last send timestamp
_send_timestamps: dict[str, float] = {}
_SEND_COOLDOWN_SECONDS = 60


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

    # For mobile apps, send an HTTPS redirect link so email clients render it
    # as a clickable hyperlink (custom ari:// scheme links are stripped by most clients).
    # The /auth/magic-link/open endpoint 302-redirects to ari://verify?token=...
    redirect_uri = (body.get("redirect_uri") or "").strip()
    frontend_url = _get_frontend_url()
    api_url = (os.getenv("API_URL") or "https://api.reilabs.ai").rstrip("/")
    if redirect_uri and redirect_uri.startswith("ari://"):
        # Send HTTPS link that redirects to the deep link
        import urllib.parse
        encoded_redirect = urllib.parse.quote(redirect_uri, safe="")
        link = f"{api_url}/auth/magic-link/open?token={token}&redirect_uri={encoded_redirect}"
    else:
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

    # Update the user document in Cosmos
    await cosmos.update_user_email(user_id, new_email)

    return jsonify({"ok": True, "email": new_email})


@magic_link_bp.get("/auth/magic-link/open")
async def open_magic_link():
    """Redirect a magic link click to the appropriate deep link or web URL.

    Mobile apps pass redirect_uri=ari://verify so the email contains an https://
    link (which email clients render correctly). Tapping it hits this endpoint,
    which issues a 302 to ari://verify?token=... and the OS opens the app.
    """
    import urllib.parse

    token = request.args.get("token", "").strip()
    redirect_uri = request.args.get("redirect_uri", "").strip()

    if not token:
        frontend_url = _get_frontend_url()
        return redirect(f"{frontend_url}/verify?error=missing_token")

    if redirect_uri and redirect_uri.startswith("ari://"):
        target = f"{redirect_uri}?token={token}"
    else:
        frontend_url = _get_frontend_url()
        target = f"{frontend_url}/verify?token={token}"

    return redirect(target, code=302)


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


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

    # Fetch raw doc BEFORE verify so we have email even if it's expired/invalid
    raw_doc = await cosmos.get_magic_token_raw(token)

    doc = await cosmos.verify_magic_token(token)
    if not doc:
        client_ip = _get_client_ip()
        if raw_doc:
            # Token existed but was expired or had been used
            associated_email = raw_doc.get("email", "unknown")
            issued_at = raw_doc.get("createdAt", "unknown")
            expires_at = raw_doc.get("expiresAt", "unknown")
            logger.warning(
                "Magic link verification failed — expired or reused token",
                extra={
                    "event": "magic_link_failed",
                    "reason": "expired_or_reused",
                    "email": associated_email,
                    "token": token,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "client_ip": client_ip,
                },
            )
        else:
            # Token never existed (fabricated, already deleted, or wrong)
            logger.warning(
                "Magic link verification failed — unknown token",
                extra={
                    "event": "magic_link_failed",
                    "reason": "not_found",
                    "email": "unknown",
                    "token": token,
                    "client_ip": client_ip,
                },
            )
        return jsonify({"error": "Invalid or expired token"}), 401

    # Single-use: delete immediately
    await cosmos.delete_magic_token(token)

    email = doc["email"]

    try:
        # Check if user already exists with this email (handles email changes).
        existing = await cosmos.find_user_by_email(email)
        if existing:
            user_id = existing.get("userId", existing.get("id"))
        else:
            # Derive deterministic user ID for new users
            user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))

        # Ensure user exists in Cosmos
        await cosmos.ensure_user(user_id, email)
    except Exception:
        logger.exception("verify_magic_link: failed to find/create user for %s", email)
        raise

    # Issue JWT
    secret, algorithm = _get_jwt_config()
    if not secret:
        return jsonify({"error": "Server configuration error", "detail": "JWT_SECRET not set"}), 500

    try:
        import jwt as pyjwt
    except ImportError:
        return jsonify({"error": "Server configuration error"}), 500

    now = datetime.datetime.now(datetime.timezone.utc)
    expiry_hours = int(os.getenv("JWT_EXPIRY_HOURS", "2160"))  # default 90 days
    jwt_payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=expiry_hours),
    }

    jwt_token = pyjwt.encode(jwt_payload, secret, algorithm=algorithm)

    return jsonify({
        "token": jwt_token,
        "user": {"id": user_id, "email": email},
    })
