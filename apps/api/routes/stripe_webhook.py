"""POST /webhook/stripe — Stripe webhook endpoint for subscription events."""

import logging
import os

from quart import Blueprint, jsonify, request

logger = logging.getLogger("api.stripe_webhook")

stripe_webhook_bp = Blueprint("stripe_webhook", __name__)


def _get_stripe_config() -> tuple[str, str]:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    return secret_key, webhook_secret


@stripe_webhook_bp.post("/webhook/stripe")
async def stripe_webhook():
    """Handle Stripe webhook events for subscription lifecycle."""
    secret_key, webhook_secret = _get_stripe_config()
    if not secret_key or not webhook_secret:
        logger.error("Stripe not configured (STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET missing)")
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        import stripe
    except ImportError:
        logger.error("stripe package not installed")
        return jsonify({"error": "Server configuration error"}), 500

    stripe.api_key = secret_key

    payload = await request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return jsonify({"error": "Invalid signature"}), 400
    except Exception:
        logger.exception("Failed to parse Stripe webhook")
        return jsonify({"error": "Invalid payload"}), 400

    event_type = event["type"]
    logger.info("Stripe webhook: %s", event_type)

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        logger.error("Cosmos DB not available for subscription update")
        return jsonify({"ok": True}), 200  # Ack to Stripe anyway

    try:
        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
        ):
            sub = event["data"]["object"]
            await _handle_subscription_update(cosmos, sub)

        elif event_type == "customer.subscription.deleted":
            sub = event["data"]["object"]
            await _handle_subscription_deleted(cosmos, sub)

        elif event_type == "customer.updated":
            customer = event["data"]["object"]
            await _handle_customer_updated(cosmos, customer)

        elif event_type == "checkout.session.completed":
            session = event["data"]["object"]
            await _handle_checkout_completed(cosmos, session)

    except Exception:
        logger.exception("Error processing Stripe event %s", event_type)

    return jsonify({"ok": True}), 200


async def _handle_subscription_update(cosmos, sub: dict) -> None:
    """Update user subscription status from a subscription object."""
    customer_id = sub.get("customer")
    if not customer_id:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("No user found for Stripe customer %s", customer_id)
        return

    user_id = user.get("userId", user.get("id"))
    stripe_data = {
        "stripe_customer_id": customer_id,
        "subscription_id": sub.get("id"),
        "subscription_status": sub.get("status"),  # active, past_due, canceled, etc.
        "plan": _extract_plan(sub),
        "subscription_expires_at": _format_timestamp(sub.get("current_period_end")),
    }

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.info("Updated subscription for user %s: status=%s", user_id, sub.get("status"))


async def _handle_subscription_deleted(cosmos, sub: dict) -> None:
    """Mark subscription as canceled."""
    customer_id = sub.get("customer")
    if not customer_id:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        return

    user_id = user.get("userId", user.get("id"))
    stripe_data = {
        "subscription_status": "canceled",
        "subscription_id": sub.get("id"),
    }

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.info("Subscription canceled for user %s", user_id)


async def _handle_customer_updated(cosmos, customer: dict) -> None:
    """Sync email change from Stripe Customer Portal to ARI."""
    customer_id = customer.get("id")
    new_email = (customer.get("email") or "").strip().lower()
    if not customer_id or not new_email:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("No user found for Stripe customer %s", customer_id)
        return

    current_email = (user.get("email") or "").strip().lower()
    if current_email == new_email:
        return  # No change

    user_id = user.get("userId", user.get("id"))

    # Check that the new email isn't already used by another ARI user
    existing = await cosmos.find_user_by_email(new_email)
    if existing and existing.get("userId", existing.get("id")) != user_id:
        logger.warning(
            "Cannot sync Stripe email change: %s already in use by another user",
            new_email,
        )
        return

    await cosmos.update_user_email(user_id, new_email)
    logger.info("Synced email change from Stripe for user %s: %s → %s", user_id, current_email, new_email)


async def _handle_checkout_completed(cosmos, session: dict) -> None:
    """Link Stripe customer to user after checkout."""
    customer_id = session.get("customer")
    customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
    subscription_id = session.get("subscription")

    if not customer_id or not customer_email:
        return

    user = await cosmos.find_user_by_email(customer_email)
    if not user:
        logger.warning("No user found for checkout email %s", customer_email)
        return

    user_id = user.get("userId", user.get("id"))
    stripe_data = {
        "stripe_customer_id": customer_id,
    }
    if subscription_id:
        stripe_data["subscription_id"] = subscription_id
        stripe_data["subscription_status"] = "active"

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.info("Linked Stripe customer %s to user %s", customer_id, user_id)


def _extract_plan(sub: dict) -> str:
    """Extract plan name from subscription items."""
    items = sub.get("items", {}).get("data", [])
    if items:
        price = items[0].get("price", {})
        return price.get("nickname") or price.get("id", "unknown")
    return "unknown"


def _format_timestamp(ts) -> str | None:
    """Convert Unix timestamp to ISO string."""
    if not ts:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
