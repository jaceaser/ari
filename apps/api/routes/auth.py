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

    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))

    cosmos = SessionsCosmosClient.get_instance()
    if cosmos:
        await cosmos.ensure_user(user_id, email)

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=24),
    }

    token = pyjwt.encode(payload, secret, algorithm=algorithm)

    return jsonify({"token": token, "user_id": user_id, "email": email})
