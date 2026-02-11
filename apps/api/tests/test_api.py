"""
Tests for the ARI API: auth, rate limiting, request validation, CORS, security headers.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

# Ensure the api directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure a clean env for each test."""
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)


@pytest.fixture
def app_client():
    """Create a fresh Quart test client."""
    # Import inside fixture so env patches take effect at module level if needed
    from app import app

    return app.test_client()


# ============================================================================
# Auth Middleware Tests
# ============================================================================


class TestAuth:
    @pytest.mark.asyncio
    async def test_health_bypasses_auth(self, app_client, monkeypatch):
        monkeypatch.setenv("API_KEYS", "secret-key-1")
        resp = await app_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_bypasses_auth(self, app_client, monkeypatch):
        monkeypatch.setenv("API_KEYS", "secret-key-1")
        resp = await app_client.get("/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self, app_client, monkeypatch):
        monkeypatch.setenv("API_KEYS", "secret-key-1")
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 401
        data = await resp.get_json()
        assert data["error"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, app_client, monkeypatch):
        monkeypatch.setenv("API_KEYS", "secret-key-1")
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key_passes_auth(self, app_client, monkeypatch):
        monkeypatch.setenv("API_KEYS", "secret-key-1,secret-key-2")
        # Will fail later (no Azure config) but should NOT be 401
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.2-chat", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            headers={"Authorization": "Bearer secret-key-2"},
        )
        assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_no_api_keys_env_disables_auth(self, app_client):
        # No API_KEYS set - auth disabled, so request passes to validation
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.2-chat", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code != 401


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_under_limit_allowed(self, app_client):
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.2-chat", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code != 429

    @pytest.mark.asyncio
    async def test_over_limit_returns_429(self, app_client):
        from middleware.rate_limit import _limiter, RATE_LIMIT
        import time

        # Fill up the rate limiter for this identifier
        key = "ip:<local>"  # Quart test client remote_addr
        now = time.monotonic()
        _limiter._requests[key] = [now] * RATE_LIMIT

        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.2-chat", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 429
        data = await resp.get_json()
        assert "retry_after" in data

        # Clean up
        _limiter._requests.clear()


# ============================================================================
# Request Validation Tests
# ============================================================================


class TestValidation:
    @pytest.mark.asyncio
    async def test_invalid_json_body(self, app_client):
        resp = await app_client.post(
            "/v1/chat/completions",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_messages_field(self, app_client):
        resp = await app_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "stream": True},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_client_model_field_is_ignored(self, app_client):
        """Server overrides model with AZURE_OPENAI_DEPLOYMENT; any client value is accepted."""
        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "evil-model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        # Should NOT be rejected — server ignores the client model field
        assert resp.status_code != 400 or "Invalid model" not in (await resp.get_json()).get("error", "")

    @pytest.mark.asyncio
    async def test_too_many_messages_rejected(self, app_client, monkeypatch):
        monkeypatch.setattr("app.MAX_MESSAGES_COUNT", 2)
        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [
                    {"role": "user", "content": "a"},
                    {"role": "assistant", "content": "b"},
                    {"role": "user", "content": "c"},
                ],
                "stream": True,
            },
        )
        assert resp.status_code == 400
        data = await resp.get_json()
        assert "Too many messages" in data["error"]

    @pytest.mark.asyncio
    async def test_oversized_message_rejected(self, app_client, monkeypatch):
        monkeypatch.setattr("app.MAX_MESSAGE_LENGTH", 10)
        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "x" * 100}],
                "stream": True,
            },
        )
        assert resp.status_code == 400
        data = await resp.get_json()
        assert "Message too long" in data["error"]

    @pytest.mark.asyncio
    async def test_stream_false_rejected(self, app_client):
        resp = await app_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.2-chat",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
        assert resp.status_code == 400


# ============================================================================
# CORS & Security Headers Tests
# ============================================================================


class TestCORSAndSecurity:
    @pytest.mark.asyncio
    async def test_cors_allowed_origin(self, app_client):
        resp = await app_client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    @pytest.mark.asyncio
    async def test_cors_disallowed_origin(self, app_client):
        resp = await app_client.get("/health", headers={"Origin": "http://evil.com"})
        assert "Access-Control-Allow-Origin" not in resp.headers

    @pytest.mark.asyncio
    async def test_security_headers_present(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "max-age" in resp.headers.get("Strict-Transport-Security", "")

    @pytest.mark.asyncio
    async def test_request_id_header(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("X-Request-ID") is not None
        assert len(resp.headers["X-Request-ID"]) == 32  # uuid4 hex

    @pytest.mark.asyncio
    async def test_options_preflight(self, app_client):
        resp = await app_client.options(
            "/v1/chat/completions",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")
