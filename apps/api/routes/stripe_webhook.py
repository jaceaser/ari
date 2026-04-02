"""POST /webhook/stripe — Stripe webhook endpoint for subscription events."""

import logging
import os
from datetime import datetime, timezone

from quart import Blueprint, jsonify, request

logger = logging.getLogger("api.stripe_webhook")

stripe_webhook_bp = Blueprint("stripe_webhook", __name__)


def _get_webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


@stripe_webhook_bp.post("/webhook/stripe")
async def stripe_webhook():
    """Handle Stripe webhook events for subscription lifecycle."""
    webhook_secret = _get_webhook_secret()
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        import stripe
    except ImportError:
        logger.error("stripe package not installed")
        return jsonify({"error": "Server configuration error"}), 500

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

    event_id = event["id"]
    event_type = event["type"]
    logger.info("Stripe webhook: %s (%s)", event_type, event_id)

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        logger.error("Cosmos DB not available for subscription update")
        return jsonify({"ok": True}), 200  # Ack to Stripe anyway

    # Idempotency: skip already-processed events
    if await cosmos.has_stripe_event_been_processed(event_id):
        logger.info("Stripe event %s already processed — skipping", event_id)
        return jsonify({"ok": True}), 200

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

        elif event_type == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            await _handle_invoice_payment_succeeded(cosmos, invoice)

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            await _handle_invoice_payment_failed(cosmos, invoice)

        # Record successful processing for idempotency
        await cosmos.record_stripe_event(event_id, event_type)

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
        # Fallback: some users have subscription_id but no stripe_customer_id (e.g. Redis migration)
        user = await cosmos.find_user_by_subscription_id(sub.get("id", ""))
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

    # Derive tier from Stripe metadata if present, otherwise fall back to plan name.
    # Without this fallback, subscriptions without a "tier" metadata key on the
    # Stripe price/product would write plan but leave tier=None in Cosmos DB.
    tier = _extract_tier(sub) or _PLAN_TO_TIER.get(stripe_data["plan"], "")
    if tier:
        stripe_data["tier"] = tier

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.info("Updated subscription for user %s: status=%s", user_id, sub.get("status"))


async def _handle_subscription_deleted(cosmos, sub: dict) -> None:
    """Mark subscription as canceled."""
    customer_id = sub.get("customer")
    if not customer_id:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        user = await cosmos.find_user_by_subscription_id(sub.get("id", ""))
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

    if not customer_id:
        return

    # Try email first, then fall back to customer ID (handles email changes)
    user = None
    if customer_email:
        user = await cosmos.find_user_by_email(customer_email)
    if not user:
        user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("No user found for checkout email=%s customer_id=%s", customer_email, customer_id)
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


async def _handle_invoice_payment_succeeded(cosmos, invoice: dict) -> None:
    """Confirm subscription as active when a payment succeeds."""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    if not customer_id:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("No user found for Stripe customer %s (invoice.payment_succeeded)", customer_id)
        return

    user_id = user.get("userId", user.get("id"))
    stripe_data: dict = {
        "stripe_customer_id": customer_id,
        "subscription_status": "active",
    }
    if subscription_id:
        stripe_data["subscription_id"] = subscription_id

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.info("Payment succeeded for user %s — subscription set to active", user_id)


async def _handle_invoice_payment_failed(cosmos, invoice: dict) -> None:
    """Mark subscription as past_due when a payment fails."""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    if not customer_id:
        return

    user = await cosmos.find_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("No user found for Stripe customer %s (invoice.payment_failed)", customer_id)
        return

    user_id = user.get("userId", user.get("id"))
    stripe_data: dict = {
        "subscription_status": "past_due",
    }
    if subscription_id:
        stripe_data["subscription_id"] = subscription_id

    await cosmos.update_user_subscription(user_id, stripe_data)
    logger.warning("Payment failed for user %s — subscription set to past_due", user_id)


def _extract_plan(sub: dict) -> str:
    """Extract plan name from subscription items."""
    items = sub.get("items", {}).get("data", [])
    if items:
        price = items[0].get("price", {})
        return price.get("nickname") or price.get("id", "unknown")
    return "unknown"


_PLAN_TO_TIER = {
    "ari_elite": "elite",
    "ari_pro": "elite",
    "ari_lite": "lite",
}


def _extract_tier(sub: dict) -> str:
    """Extract and normalize tier from subscription or price metadata.

    Checks subscription metadata, then price metadata, then product metadata.
    Normalizes values like 'ari_elite' → 'elite' to match _TIER_TOOLS keys.
    """
    raw = ""
    # Check subscription-level metadata first
    raw = (sub.get("metadata") or {}).get("tier", "").strip().lower()
    if not raw:
        # Fall back to price metadata
        items = sub.get("items", {}).get("data", [])
        if items:
            price = items[0].get("price", {})
            raw = (price.get("metadata") or {}).get("tier", "").strip().lower()
            if not raw:
                product = price.get("product") or {}
                if isinstance(product, dict):
                    raw = (product.get("metadata") or {}).get("tier", "").strip().lower()
    # Normalize ari_* prefixed values to canonical tier names
    return _PLAN_TO_TIER.get(raw, raw)


def _format_timestamp(ts) -> str | None:
    """Convert Unix timestamp to ISO string."""
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
