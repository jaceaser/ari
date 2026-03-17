"""Billing endpoints for subscription status and checkout.

GET  /billing/status          — current user's subscription status
POST /billing/create-checkout — create Stripe Checkout Session
POST /billing/create-portal   — create Stripe Customer Portal session
"""

import logging
import os

from quart import Blueprint, jsonify, request

logger = logging.getLogger("api.billing")

billing_bp = Blueprint("billing", __name__)


def _user_id() -> str:
    return getattr(request, "user_id", "")


def _user_email() -> str:
    return getattr(request, "user_email", "")


@billing_bp.get("/billing/me")
async def users_me():
    """Return lightweight profile: email + tier. Used by mobile settings screen."""
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    email = _user_email()

    # Re-use the same cached tier logic as the guardrails middleware
    from app import _get_user_tier
    tier = await _get_user_tier(user_id)

    return jsonify({"email": email, "tier": tier or "free"})


@billing_bp.get("/billing/status")
async def billing_status():
    """Return the current user's subscription status."""
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"active": False, "plan": None, "expires_at": None})

    sub = await cosmos.get_user_subscription(user_id)
    if not sub:
        return jsonify({"active": False, "plan": None, "expires_at": None})

    active = sub.get("subscription_status") in ("active", "trialing")
    return jsonify({
        "active": active,
        "plan": sub.get("plan"),
        "status": sub.get("subscription_status"),
        "expires_at": sub.get("subscription_expires_at"),
        "stripe_customer_id": sub.get("stripe_customer_id"),
        "tier": sub.get("tier"),
        "updated_at": sub.get("updated_at"),
    })


@billing_bp.post("/billing/create-checkout")
async def create_checkout():
    """Create a Stripe Checkout Session and return the URL."""
    user_email = _user_email()

    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    price_id = os.getenv("STRIPE_PRICE_ID", "").strip()
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if not secret_key or not price_id:
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        import stripe
    except ImportError:
        return jsonify({"error": "Server configuration error"}), 500

    stripe.api_key = secret_key

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{frontend_url}/billing?success=true",
            cancel_url=f"{frontend_url}/billing?canceled=true",
            **({"customer_email": user_email} if user_email else {}),
        )
    except Exception:
        logger.exception("Failed to create Stripe checkout session")
        return jsonify({"error": "Failed to create checkout session"}), 500

    return jsonify({"url": session.url})


@billing_bp.post("/billing/create-portal")
async def create_portal():
    """Create a Stripe Customer Portal session for managing subscription."""
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if not secret_key:
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        import stripe
    except ImportError:
        return jsonify({"error": "Server configuration error"}), 500

    stripe.api_key = secret_key

    # Look up the user's Stripe customer ID
    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Server configuration error"}), 500

    sub = await cosmos.get_user_subscription(user_id)
    customer_id = sub.get("stripe_customer_id") if sub else None

    if not customer_id:
        return jsonify({"error": "No subscription found. Please subscribe first."}), 404

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{frontend_url}/billing",
        )
    except Exception:
        logger.exception("Failed to create Stripe portal session")
        return jsonify({"error": "Failed to create portal session"}), 500

    return jsonify({"url": portal_session.url})
