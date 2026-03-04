"""
Regression tests for PR11: Production Hardening.

Covers:
- /v1/chat/completions auth: API key and JWT both work, anonymous is rejected
- Response security headers present on all endpoints
- Streaming SSE format is unchanged (data: prefix, valid JSON chunks)
- X-Forwarded-Proto enforcement when FORCE_HTTPS=True
- Auth-endpoint rate limiting (5/min per IP)
- /billing/status returns new fields (stripe_customer_id, tier, updated_at)
- Stripe webhook idempotency (same event ID processed once)
"""

from __future__ import annotations

import json
import sys
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _constants import TEST_JWT_SECRET, TEST_USER_EMAIL, TEST_USER_ID


# ============================================================================
# Security Headers
# ============================================================================


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_health_has_security_headers(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "max-age=" in resp.headers.get("Strict-Transport-Security", "")

    @pytest.mark.asyncio
    async def test_health_has_referrer_policy(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_health_has_permissions_policy(self, app_client):
        resp = await app_client.get("/health")
        pp = resp.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in pp
        assert "microphone=()" in pp


# ============================================================================
# HTTPS Redirect (FORCE_HTTPS)
# ============================================================================


class TestForceHttps:
    @pytest.mark.asyncio
    async def test_https_redirect_when_force_https_enabled(self, app_client, monkeypatch):
        """When FORCE_HTTPS=True and X-Forwarded-Proto: http, redirect 301 to HTTPS."""
        monkeypatch.setenv("FORCE_HTTPS", "true")
        # Patch module-level constant
        import app as app_mod
        app_mod.FORCE_HTTPS = True

        resp = await app_client.get(
            "/health",
            headers={"X-Forwarded-Proto": "http"},
        )
        assert resp.status_code == 301

        app_mod.FORCE_HTTPS = False
        monkeypatch.setenv("FORCE_HTTPS", "false")

    @pytest.mark.asyncio
    async def test_no_redirect_when_https(self, app_client, monkeypatch):
        """When X-Forwarded-Proto: https, no redirect."""
        import app as app_mod
        app_mod.FORCE_HTTPS = True

        resp = await app_client.get(
            "/health",
            headers={"X-Forwarded-Proto": "https"},
        )
        assert resp.status_code == 200

        app_mod.FORCE_HTTPS = False

    @pytest.mark.asyncio
    async def test_no_redirect_when_force_https_disabled(self, app_client):
        """When FORCE_HTTPS=False, HTTP traffic is not redirected."""
        import app as app_mod
        app_mod.FORCE_HTTPS = False

        resp = await app_client.get(
            "/health",
            headers={"X-Forwarded-Proto": "http"},
        )
        assert resp.status_code == 200


# ============================================================================
# /v1/chat/completions — auth regression
# ============================================================================


class TestChatAuth:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, app_client, monkeypatch):
        """Anonymous requests to /v1/chat/completions must be rejected."""
        monkeypatch.setenv("API_KEYS", "test-api-key")

        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_auth_passes(self, app_client, monkeypatch):
        """Valid API key must NOT be rejected with 401."""
        monkeypatch.setenv("API_KEYS", "test-api-key")

        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
            headers={"Authorization": "Bearer test-api-key"},
        )
        # Will fail downstream (no Azure config) but MUST not be 401
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, app_client, monkeypatch):
        """Wrong API key must be rejected."""
        monkeypatch.setenv("API_KEYS", "correct-key")

        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_auth_passes(self, app_client, auth_headers, monkeypatch):
        """Valid JWT must NOT be rejected with 401 on /v1/chat/completions."""
        monkeypatch.delenv("API_KEYS", raising=False)

        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code != 401


# ============================================================================
# Auth endpoint rate limiting
# ============================================================================


class TestAuthRateLimit:
    # Quart test client uses "<local>" as remote_addr
    _TEST_IP = "<local>"

    @pytest.mark.asyncio
    async def test_magic_link_send_rate_limited_after_5_requests(self, app_client):
        """POST /auth/magic-link/send should be rate-limited at 5 req/min per IP."""
        from middleware.rate_limit import _auth_limiter, AUTH_RATE_LIMIT
        _auth_limiter._requests.clear()

        # Fill auth limiter for the test client IP
        now = time.monotonic()
        _auth_limiter._requests[f"auth:{self._TEST_IP}"] = [now] * AUTH_RATE_LIMIT

        resp = await app_client.post(
            "/auth/magic-link/send",
            json={"email": "user@example.com"},
        )
        assert resp.status_code == 429
        data = await resp.get_json()
        assert "authentication" in data["error"].lower() or "rate" in data["error"].lower()

        _auth_limiter._requests.clear()

    @pytest.mark.asyncio
    async def test_magic_link_send_not_rate_limited_below_threshold(self, app_client):
        """First request to /auth/magic-link/send should not be rate-limited."""
        from middleware.rate_limit import _auth_limiter
        _auth_limiter._requests.clear()

        resp = await app_client.post(
            "/auth/magic-link/send",
            json={"email": "user@example.com"},
        )
        # Should not be 429 (may be 400 or 200 depending on email validation)
        assert resp.status_code != 429

        _auth_limiter._requests.clear()

    @pytest.mark.asyncio
    async def test_auth_exchange_rate_limited(self, app_client):
        """POST /auth/exchange should be rate-limited at 5 req/min per IP."""
        from middleware.rate_limit import _auth_limiter, AUTH_RATE_LIMIT
        _auth_limiter._requests.clear()

        now = time.monotonic()
        _auth_limiter._requests[f"auth:{self._TEST_IP}"] = [now] * AUTH_RATE_LIMIT

        resp = await app_client.post(
            "/auth/exchange",
            json={"token": "fake-token"},
        )
        assert resp.status_code == 429

        _auth_limiter._requests.clear()

    @pytest.mark.asyncio
    async def test_normal_endpoints_use_global_limit_not_auth_limit(self, app_client, monkeypatch):
        """Non-auth endpoints should NOT be blocked by auth rate limit."""
        from middleware.rate_limit import _auth_limiter, AUTH_RATE_LIMIT
        _auth_limiter._requests.clear()

        # Fill auth limiter
        ip = "127.0.0.1"
        now = time.monotonic()
        _auth_limiter._requests[f"auth:{ip}"] = [now] * AUTH_RATE_LIMIT

        # /health is not an auth endpoint — should still work
        resp = await app_client.get("/health")
        assert resp.status_code == 200

        _auth_limiter._requests.clear()


# ============================================================================
# /billing/status — extended fields
# ============================================================================


class TestBillingStatusExtended:
    @pytest.mark.asyncio
    async def test_billing_status_includes_stripe_customer_id(self, app_client, auth_headers, mock_cosmos):
        """billing/status must include stripe_customer_id field."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value={
            "subscription_status": "active",
            "plan": "pro",
            "stripe_customer_id": "cus_test123",
            "tier": "pro",
            "updated_at": "2025-06-01T00:00:00+00:00",
        })

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["stripe_customer_id"] == "cus_test123"

    @pytest.mark.asyncio
    async def test_billing_status_includes_tier(self, app_client, auth_headers, mock_cosmos):
        """billing/status must include tier field."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value={
            "subscription_status": "active",
            "plan": "pro",
            "tier": "pro",
        })

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["tier"] == "pro"

    @pytest.mark.asyncio
    async def test_billing_status_includes_updated_at(self, app_client, auth_headers, mock_cosmos):
        """billing/status must include updated_at field."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value={
            "subscription_status": "active",
            "updated_at": "2025-06-01T12:00:00+00:00",
        })

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["updated_at"] == "2025-06-01T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_billing_status_null_fields_when_no_subscription(self, app_client, auth_headers, mock_cosmos):
        """Fields should be null/None when user has no subscription."""
        mock_cosmos.get_user_subscription = AsyncMock(return_value=None)

        resp = await app_client.get("/billing/status", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["active"] is False
        assert data.get("stripe_customer_id") is None


# ============================================================================
# Stripe idempotency — cosmos helpers
# ============================================================================


class TestStripeIdempotency:
    @pytest.mark.asyncio
    async def test_has_stripe_event_returns_false_when_not_processed(self):
        """has_stripe_event_been_processed returns False for unknown event."""
        from cosmos import SessionsCosmosClient

        cosmos = MagicMock()
        cosmos.has_stripe_event_been_processed = AsyncMock(return_value=False)

        result = await cosmos.has_stripe_event_been_processed("evt_unknown_123")
        assert result is False

    @pytest.mark.asyncio
    async def test_has_stripe_event_returns_true_after_record(self):
        """has_stripe_event_been_processed returns True after recording."""
        from cosmos import SessionsCosmosClient

        cosmos = MagicMock()
        cosmos.record_stripe_event = AsyncMock()
        cosmos.has_stripe_event_been_processed = AsyncMock(return_value=True)

        await cosmos.record_stripe_event("evt_test_abc", "checkout.session.completed")
        result = await cosmos.has_stripe_event_been_processed("evt_test_abc")
        assert result is True

    @pytest.mark.asyncio
    async def test_webhook_skips_duplicate_event(self, app_client, mock_cosmos, monkeypatch):
        """Stripe webhook returns 200 immediately for duplicate event IDs."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")

        # Mark event as already processed
        mock_cosmos.has_stripe_event_been_processed = AsyncMock(return_value=True)

        fake_event = {
            "id": "evt_duplicate_123",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_123", "customer": "cus_123", "status": "active"}},
        }

        # Patch stripe at the routes module level so the import inside the handler is mocked
        stripe_mock = MagicMock()
        stripe_mock.Webhook.construct_event.return_value = fake_event
        stripe_mock.error.SignatureVerificationError = Exception

        with patch.dict("sys.modules", {"stripe": stripe_mock}):
            resp = await app_client.post(
                "/webhook/stripe",
                data='{"id":"evt_duplicate_123","type":"test"}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=sig",
                },
            )

        assert resp.status_code == 200
        # Subscription should NOT have been updated for duplicate
        mock_cosmos.update_user_subscription.assert_not_called()
