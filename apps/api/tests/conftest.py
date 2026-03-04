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
    # Clear rate limiters between tests
    from middleware.rate_limit import _limiter, _auth_limiter
    _limiter._requests.clear()
    _auth_limiter._requests.clear()


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
    })
    mock.get_sessions = AsyncMock(return_value=[
        {
            "id": TEST_SESSION_ID,
            "type": "session",
            "userId": TEST_USER_ID,
            "title": "Test Session",
            "status": "active",
            "createdAt": "2025-01-01T00:00:00+00:00",
        }
    ])
    mock.get_session = AsyncMock(return_value={
        "id": TEST_SESSION_ID,
        "type": "session",
        "userId": TEST_USER_ID,
        "title": "Test Session",
        "status": "active",
        "createdAt": "2025-01-01T00:00:00+00:00",
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
    # Frontend data persistence methods (PR9a)
    mock.save_messages = AsyncMock()
    mock.get_messages_by_chat_id = AsyncMock(return_value=[])
    mock.get_message_by_id = AsyncMock(return_value=None)
    mock.update_message = AsyncMock()
    mock.delete_messages_after_timestamp = AsyncMock()
    mock.get_message_count = AsyncMock(return_value=0)
    mock.save_document = AsyncMock()
    mock.get_document_by_id = AsyncMock(return_value=None)
    mock.get_documents_by_id = AsyncMock(return_value=[])
    mock.delete_documents_after_timestamp = AsyncMock()
    mock.save_suggestions = AsyncMock()
    mock.get_suggestions_by_document_id = AsyncMock(return_value=[])
    mock.vote_message = AsyncMock()
    mock.get_votes_by_chat_id = AsyncMock(return_value=[])

    # Magic link methods (PR9c)
    mock.store_magic_token = AsyncMock(return_value={})
    mock.verify_magic_token = AsyncMock(return_value=None)
    mock.delete_magic_token = AsyncMock()

    # Subscription methods (PR9d)
    mock.get_user_subscription = AsyncMock(return_value=None)
    mock.update_user_subscription = AsyncMock()
    mock.find_user_by_email = AsyncMock(return_value=None)
    mock.find_user_by_stripe_customer = AsyncMock(return_value=None)

    # Stripe idempotency (PR11)
    mock.has_stripe_event_been_processed = AsyncMock(return_value=False)
    mock.record_stripe_event = AsyncMock()

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
