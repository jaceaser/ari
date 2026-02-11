"""Tests for JWT authentication middleware (Phase 2 endpoints)."""

import pytest

from _constants import TEST_USER_EMAIL, TEST_USER_ID


class TestJWTAuth:
    """JWT auth applies to /sessions/*, /lead-runs/*, /auth/* endpoints."""

    @pytest.mark.asyncio
    async def test_sessions_requires_jwt(self, app_client):
        """GET /sessions without JWT returns 401."""
        resp = await app_client.get("/sessions")
        assert resp.status_code == 401
        data = await resp.get_json()
        assert data["error"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_lead_runs_requires_jwt(self, app_client):
        """GET /lead-runs without JWT returns 401."""
        resp = await app_client.get("/lead-runs")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_jwt_passes(self, app_client, auth_headers):
        """GET /sessions with valid JWT succeeds."""
        resp = await app_client.get("/sessions", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_401(self, app_client, expired_jwt_token):
        """Expired JWT returns 401."""
        resp = await app_client.get(
            "/sessions",
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
        )
        assert resp.status_code == 401
        data = await resp.get_json()
        assert "expired" in data.get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_invalid_jwt_returns_401(self, app_client):
        """Garbage JWT returns 401."""
        resp = await app_client.get(
            "/sessions",
            headers={"Authorization": "Bearer not.a.valid.jwt"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_sets_user_id(self, app_client, auth_headers, mock_cosmos):
        """Valid JWT sets request.user_id which is used for Cosmos queries."""
        resp = await app_client.get("/sessions", headers=auth_headers)
        assert resp.status_code == 200
        # Verify Cosmos was called with the correct user_id
        mock_cosmos.get_sessions.assert_called_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_v1_endpoint_uses_api_key_not_jwt(self, app_client, monkeypatch):
        """Legacy /v1/* endpoints use API key auth, not JWT."""
        monkeypatch.setenv("API_KEYS", "test-api-key")
        # JWT should NOT work for /v1/*
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.2-chat", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            headers={"Authorization": "Bearer some-jwt-token"},
        )
        # Should get 401 because "some-jwt-token" is not in API_KEYS
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_disabled_when_no_secret(self, app_client, monkeypatch):
        """When JWT_SECRET is unset, JWT middleware passes through (doesn't block)."""
        monkeypatch.setenv("JWT_SECRET", "")
        # Reset the cached secret
        import middleware.auth as auth_mod
        auth_mod._JWT_SECRET = None

        resp = await app_client.get("/sessions")
        # JWT middleware passes through, but route returns 401 since user_id not set.
        # The key assertion: it's the route's 401 (no user_id), not middleware's 401 (token error).
        data = await resp.get_json()
        assert resp.status_code == 401
        assert data["error"] == "Unauthorized"
        # Middleware would include "detail" with token-specific message; route does not.
        assert "detail" not in data

    @pytest.mark.asyncio
    async def test_health_bypasses_jwt(self, app_client):
        """Health endpoint doesn't require JWT."""
        resp = await app_client.get("/health")
        assert resp.status_code == 200
