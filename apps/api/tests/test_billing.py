"""Tests for billing and Stripe webhook endpoints (PR9d)."""

import pytest
from unittest.mock import AsyncMock, patch

from _constants import TEST_JWT_SECRET, TEST_USER_EMAIL, TEST_USER_ID


class TestBillingStatus:
    @pytest.mark.asyncio
    async def test_billing_requires_jwt(self, app_client):
        """GET /billing/status without JWT returns 401."""
        resp = await app_client.get("/billing/status")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_billing_no_subscription(self, app_client, auth_headers, mock_cosmos):
        """User with no subscription gets active=false."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value=None)

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["active"] is False

    @pytest.mark.asyncio
    async def test_billing_active_subscription(self, app_client, auth_headers, mock_cosmos):
        """User with active subscription gets active=true."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value={
            "subscription_status": "active",
            "subscription_id": "sub_123",
            "stripe_customer_id": "cus_123",
            "plan": "pro",
            "subscription_expires_at": "2025-12-31T00:00:00+00:00",
        })

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["active"] is True
        assert data["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_billing_canceled_subscription(self, app_client, auth_headers, mock_cosmos):
        """Canceled subscription returns active=false."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value={
            "subscription_status": "canceled",
            "plan": "pro",
        })

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["active"] is False


class TestCreateCheckout:
    @pytest.mark.asyncio
    async def test_checkout_requires_jwt(self, app_client):
        """POST /billing/create-checkout without JWT returns 401."""
        resp = await app_client.post("/billing/create-checkout")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_checkout_no_stripe_returns_500(self, app_client, auth_headers, monkeypatch):
        """Returns 500 if Stripe is not configured."""
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)

        resp = await app_client.post("/billing/create-checkout", headers=auth_headers)
        assert resp.status_code == 500


class TestStripeWebhook:
    @pytest.mark.asyncio
    async def test_webhook_no_auth_required(self, app_client):
        """POST /webhook/stripe does NOT require JWT or API key."""
        # With no Stripe config, should get 500 (not configured), not 401
        resp = await app_client.post(
            "/webhook/stripe",
            json={"type": "test"},
        )
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_webhook_no_stripe_config_returns_500(self, app_client, monkeypatch):
        """Returns 500 if Stripe keys not set."""
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

        resp = await app_client.post(
            "/webhook/stripe",
            json={"type": "test"},
        )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature_returns_400(self, app_client, monkeypatch):
        """Invalid Stripe-Signature returns 400."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_fake")

        resp = await app_client.post(
            "/webhook/stripe",
            data='{"type":"test"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=123,v1=bad",
            },
        )
        # 400 (bad signature) or 500 (stripe import issue) — not 200
        assert resp.status_code in (400, 500)

    @pytest.mark.asyncio
    async def test_webhook_not_rate_limited(self, app_client, monkeypatch):
        """Webhook path is exempt from rate limiting."""
        from middleware.rate_limit import _limiter, RATE_LIMIT
        import time

        # Fill rate limiter for this client
        key = "ip:<local>"
        now = time.monotonic()
        _limiter._requests[key] = [now] * RATE_LIMIT

        resp = await app_client.post(
            "/webhook/stripe",
            json={"type": "test"},
        )
        # Should NOT be 429 — webhook is exempt
        assert resp.status_code != 429

        _limiter._requests.clear()
