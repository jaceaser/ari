"""Tests for magic link authentication endpoints (PR9c)."""

import pytest
from unittest.mock import AsyncMock, patch

from _constants import TEST_JWT_SECRET, TEST_USER_EMAIL, TEST_USER_ID


class TestMagicLinkSend:
    @pytest.mark.asyncio
    async def test_send_requires_email(self, app_client):
        """POST /auth/magic-link/send without email returns 400."""
        resp = await app_client.post(
            "/auth/magic-link/send",
            json={},
        )
        assert resp.status_code == 400
        data = await resp.get_json()
        assert "email" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_send_rejects_invalid_email(self, app_client):
        """POST /auth/magic-link/send with bad email returns 400."""
        resp = await app_client.post(
            "/auth/magic-link/send",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_success(self, app_client, mock_cosmos):
        """POST /auth/magic-link/send stores token and returns ok."""
        mock_cosmos.store_magic_token = AsyncMock(return_value={})

        with patch("routes.magic_link._send_email", new_callable=AsyncMock):
            resp = await app_client.post(
                "/auth/magic-link/send",
                json={"email": TEST_USER_EMAIL},
            )

        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["ok"] is True
        mock_cosmos.store_magic_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_rate_limited(self, app_client, mock_cosmos):
        """Second send within 60s returns 429."""
        mock_cosmos.store_magic_token = AsyncMock(return_value={})

        with patch("routes.magic_link._send_email", new_callable=AsyncMock):
            # First request succeeds
            resp1 = await app_client.post(
                "/auth/magic-link/send",
                json={"email": "ratelimit@test.com"},
            )
            assert resp1.status_code == 200

            # Second request within cooldown returns 429
            resp2 = await app_client.post(
                "/auth/magic-link/send",
                json={"email": "ratelimit@test.com"},
            )
            assert resp2.status_code == 429
            data = await resp2.get_json()
            assert "retry_after" in data

        # Clean up rate limit state
        from routes.magic_link import _send_timestamps
        _send_timestamps.pop("ratelimit@test.com", None)

    @pytest.mark.asyncio
    async def test_send_no_cosmos_returns_500(self, app_client, mock_cosmos):
        """Returns 500 if Cosmos is not configured."""
        # Temporarily make get_instance return None
        with patch("cosmos.SessionsCosmosClient.get_instance", return_value=None):
            resp = await app_client.post(
                "/auth/magic-link/send",
                json={"email": "nocosmos@test.com"},
            )
        assert resp.status_code == 500

        from routes.magic_link import _send_timestamps
        _send_timestamps.pop("nocosmos@test.com", None)


class TestMagicLinkVerify:
    @pytest.mark.asyncio
    async def test_verify_requires_token(self, app_client):
        """POST /auth/magic-link/verify without token returns 400."""
        resp = await app_client.post(
            "/auth/magic-link/verify",
            json={},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, app_client, mock_cosmos):
        """POST /auth/magic-link/verify with bad token returns 401."""
        mock_cosmos.verify_magic_token = AsyncMock(return_value=None)

        resp = await app_client.post(
            "/auth/magic-link/verify",
            json={"token": "bad-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_success(self, app_client, mock_cosmos):
        """Valid token returns JWT and user info."""
        mock_cosmos.verify_magic_token = AsyncMock(return_value={
            "id": "token-123",
            "email": TEST_USER_EMAIL,
            "type": "magic_token",
        })
        mock_cosmos.delete_magic_token = AsyncMock()
        mock_cosmos.ensure_user = AsyncMock(return_value={
            "id": TEST_USER_ID, "email": TEST_USER_EMAIL,
        })

        resp = await app_client.post(
            "/auth/magic-link/verify",
            json={"token": "valid-token"},
        )
        assert resp.status_code == 200
        data = await resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == TEST_USER_EMAIL

        # Token should be deleted (single-use)
        mock_cosmos.delete_magic_token.assert_called_once_with("valid-token")

    @pytest.mark.asyncio
    async def test_verify_no_jwt_secret_returns_500(self, app_client, mock_cosmos, monkeypatch):
        """Returns 500 if JWT_SECRET is not set."""
        monkeypatch.setenv("JWT_SECRET", "")
        import middleware.auth as auth_mod
        auth_mod._JWT_SECRET = None

        mock_cosmos.verify_magic_token = AsyncMock(return_value={
            "id": "token-123",
            "email": TEST_USER_EMAIL,
        })
        mock_cosmos.delete_magic_token = AsyncMock()
        mock_cosmos.ensure_user = AsyncMock()

        resp = await app_client.post(
            "/auth/magic-link/verify",
            json={"token": "valid-token"},
        )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_send_and_verify_no_auth_required(self, app_client, monkeypatch):
        """Magic link endpoints are accessible without JWT (not blocked by auth middleware)."""
        monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
        import middleware.auth as auth_mod
        auth_mod._JWT_SECRET = None

        # Send — should NOT get auth middleware 401 "Missing bearer token"
        resp = await app_client.post(
            "/auth/magic-link/send",
            json={"email": "noauth@test.com"},
        )
        if resp.status_code == 401:
            data = await resp.get_json()
            # Auth middleware says "Missing bearer token"; route logic never returns 401 on send
            assert "bearer" not in data.get("error", "").lower(), \
                "Send endpoint should not require JWT auth"

        # Verify — may return 401 for invalid token, but NOT for missing JWT
        resp = await app_client.post(
            "/auth/magic-link/verify",
            json={"token": "anything"},
        )
        if resp.status_code == 401:
            data = await resp.get_json()
            # Route returns "Invalid or expired token"; auth middleware returns "Missing bearer token"
            assert "bearer" not in data.get("error", "").lower(), \
                "Verify endpoint should not require JWT auth"

        from routes.magic_link import _send_timestamps
        _send_timestamps.pop("noauth@test.com", None)
