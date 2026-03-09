"""POST /auth/exchange — issue JWT from existing session cookie."""

import datetime
import logging
import os
import uuid

from quart import jsonify, request, session

from . import auth_bp

logger = logging.getLogger("api.auth.routes")


@auth_bp.post("/auth/exchange")
async def exchange():
    """
    Exchange an existing authenticated session cookie for a JWT.

    No request body required. Reads session['user_email'].
    Returns {token, user_id, email}. 401 if no session.
    """
    email = session.get("user_email")
    if not email:
        return jsonify({"error": "Unauthorized", "detail": "No authenticated session"}), 401

    # Import here to avoid circular import with app.py
    try:
        import jwt as pyjwt
    except ImportError:
        logger.error("PyJWT not installed; cannot issue JWT.")
        return jsonify({"error": "Server configuration error"}), 500

    secret = os.getenv("JWT_SECRET", "").strip()
    algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip()

    if not secret:
        logger.error("JWT_SECRET not set; cannot issue token.")
        return jsonify({"error": "Server configuration error"}), 500

    # Ensure user exists in Cosmos (if configured)
    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()

    # Check if user already exists with this email (handles email changes)
    # If they changed their email, the user doc has the new email but the old user_id.
    # Using find_user_by_email ensures we reuse the existing account.
    user_id = None
    if cosmos:
        existing = await cosmos.find_user_by_email(email)
        if existing:
            user_id = existing.get("userId", existing.get("id"))

    # Fall back to deterministic ID for new users
    if not user_id:
        user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))

    if cosmos:
        await cosmos.ensure_user(user_id, email)

    now = datetime.datetime.now(datetime.timezone.utc)
    expiry_hours = int(os.getenv("JWT_EXPIRY_HOURS", "2160"))  # default 90 days
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=expiry_hours),
    }

    token = pyjwt.encode(payload, secret, algorithm=algorithm)

    return jsonify({"token": token, "user_id": user_id, "email": email})
