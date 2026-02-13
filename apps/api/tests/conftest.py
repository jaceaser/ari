"""Shared fixtures for Phase 2 API tests."""

import datetime
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the tests and api directories are importable
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _constants import TEST_JWT_SECRET, TEST_LEAD_RUN_ID, TEST_SESSION_ID, TEST_USER_EMAIL, TEST_USER_ID


# ── Fixtures ──


@pytest.fixture(autouse=True)
def _phase2_env(monkeypatch):
    """Set up Phase 2 env vars for all tests."""
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    # Disable API key auth so it doesn't interfere
    monkeypatch.delenv("API_KEYS", raising=False)
    # Reset cached JWT config so env changes take effect
    import middleware.auth as auth_mod
    auth_mod._JWT_SECRET = None


@pytest.fixture
def jwt_token():
    """Generate a valid JWT for testing."""
    import jwt as pyjwt

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "iat": now,
        "exp": now + datetime.timedelta(hours=1),
    }
    return pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def expired_jwt_token():
    """Generate an expired JWT for testing."""
    import jwt as pyjwt

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "iat": now - datetime.timedelta(hours=2),
        "exp": now - datetime.timedelta(hours=1),
    }
    return pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def auth_headers(jwt_token):
    """Standard auth headers with valid JWT."""
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture
def mock_cosmos():
    """Mock SessionsCosmosClient with standard return values."""
    mock = MagicMock()

    # Default returns
    mock.ensure_user = AsyncMock(return_value={"id": TEST_USER_ID, "email": TEST_USER_EMAIL})
    mock.create_session = AsyncMock(return_value={
        "id": TEST_SESSION_ID,
        "type": "session",
        "userId": TEST_USER_ID,
        "title": None,
        "status": "active",
        "createdAt": "2025-01-01T00:00:00+00:00",
        "sealedAt": None,
    })
    mock.get_sessions = AsyncMock(return_value=[
        {
            "id": TEST_SESSION_ID,
            "type": "session",
            "userId": TEST_USER_ID,
            "title": "Test Session",
            "status": "active",
            "createdAt": "2025-01-01T00:00:00+00:00",
            "sealedAt": None,
        }
    ])
    mock.get_session = AsyncMock(return_value={
        "id": TEST_SESSION_ID,
        "type": "session",
        "userId": TEST_USER_ID,
        "title": "Test Session",
        "status": "active",
        "createdAt": "2025-01-01T00:00:00+00:00",
        "sealedAt": None,
    })
    mock.seal_session = AsyncMock(return_value={
        "id": TEST_SESSION_ID,
        "status": "sealed",
        "sealedAt": "2025-01-01T01:00:00+00:00",
    })
    mock.create_message = AsyncMock(return_value={
        "id": "msg-123",
        "type": "message",
        "role": "user",
        "content": "hello",
        "createdAt": "2025-01-01T00:00:00+00:00",
    })
    mock.get_messages = AsyncMock(return_value=[
        {
            "id": "msg-1",
            "role": "user",
            "content": "hello",
            "createdAt": "2025-01-01T00:00:00+00:00",
        },
        {
            "id": "msg-2",
            "role": "assistant",
            "content": "hi there",
            "createdAt": "2025-01-01T00:00:01+00:00",
        },
    ])
    mock.get_recent_messages = AsyncMock(return_value=[
        {
            "id": "msg-1",
            "role": "user",
            "content": "hello",
            "createdAt": "2025-01-01T00:00:00+00:00",
        },
    ])
    mock.create_lead_run = AsyncMock(return_value={"id": TEST_LEAD_RUN_ID})
    mock.get_lead_runs = AsyncMock(return_value=[
        {
            "id": TEST_LEAD_RUN_ID,
            "summary": "Lead run in Miami",
            "location": "Miami, FL",
            "strategy": "motivated_sellers",
            "resultCount": 25,
            "createdAt": "2025-01-01T00:00:00+00:00",
        }
    ])
    mock.get_lead_run = AsyncMock(return_value={
        "id": TEST_LEAD_RUN_ID,
        "summary": "Lead run in Miami",
        "location": "Miami, FL",
        "strategy": "motivated_sellers",
        "resultCount": 25,
        "fileUrl": f"https://storage.example.com/leads/{TEST_LEAD_RUN_ID}.csv",
        "filters": {"min_equity": 50},
        "createdAt": "2025-01-01T00:00:00+00:00",
    })

    return mock


@pytest.fixture
def app_client(mock_cosmos):
    """Create a Quart test client with mocked Cosmos."""
    with patch("cosmos.SessionsCosmosClient.get_instance", return_value=mock_cosmos):
        # Also clear the cached singleton
        from cosmos import SessionsCosmosClient
        SessionsCosmosClient._instance = None

        from app import app
        yield app.test_client()

        # Reset singleton after test
        SessionsCosmosClient._instance = None
