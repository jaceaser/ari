"""Tests for session CRUD, message endpoints, and session ID hardening."""

import datetime
import uuid

import pytest

from _constants import (
    TEST_JWT_SECRET,
    TEST_SESSION_ID,
    TEST_USER_EMAIL,
    TEST_USER_EMAIL_B,
    TEST_USER_ID,
    TEST_USER_ID_B,
)


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.post("/sessions", headers=auth_headers)
        assert resp.status_code == 201
        data = await resp.get_json()
        assert "id" in data
        assert "created_at" in data
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title=None, session_id=None)

    @pytest.mark.asyncio
    async def test_create_session_with_title(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.post(
            "/sessions",
            json={"title": "My Session"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title="My Session", session_id=None)

    @pytest.mark.asyncio
    async def test_create_session_with_client_id(self, app_client, auth_headers, mock_cosmos):
        client_id = str(uuid.uuid4())
        resp = await app_client.post(
            "/sessions",
            json={"id": client_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title=None, session_id=client_id)

    @pytest.mark.asyncio
    async def test_list_sessions(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get("/sessions", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == TEST_SESSION_ID
        assert data[0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_session(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get(f"/sessions/{TEST_SESSION_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["id"] == TEST_SESSION_ID

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        missing_id = str(uuid.uuid4())
        resp = await app_client.get(f"/sessions/{missing_id}", headers=auth_headers)
        assert resp.status_code == 404



class TestMessages:
    @pytest.mark.asyncio
    async def test_list_messages(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get(f"/sessions/{TEST_SESSION_ID}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_list_messages_session_not_found(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        missing_id = str(uuid.uuid4())
        resp = await app_client.get(f"/sessions/{missing_id}/messages", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_missing_content(self, app_client, auth_headers):
        resp = await app_client.post(
            f"/sessions/{TEST_SESSION_ID}/messages",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, app_client, auth_headers):
        resp = await app_client.post(
            f"/sessions/{TEST_SESSION_ID}/messages",
            json={"content": "  "},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_session(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        missing_id = str(uuid.uuid4())
        resp = await app_client.post(
            f"/sessions/{missing_id}/messages",
            json={"content": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestSessionIdHardening:
    """Validate format, ownership, and cross-user isolation for session IDs."""

    # ── Format validation ──

    @pytest.mark.asyncio
    async def test_create_session_invalid_id_format(self, app_client, auth_headers):
        """Reject non-UUID session IDs."""
        resp = await app_client.post(
            "/sessions",
            json={"id": "not-a-uuid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = await resp.get_json()
        assert "Invalid session ID format" in data["error"]

    @pytest.mark.asyncio
    async def test_create_session_id_injection_attempt(self, app_client, auth_headers):
        """Reject IDs with SQL/NoSQL injection patterns."""
        for malicious_id in [
            "'; DROP TABLE sessions; --",
            "../../../etc/passwd",
            "<script>alert(1)</script>",
            "a" * 1000,
            "",
        ]:
            resp = await app_client.post(
                "/sessions",
                json={"id": malicious_id},
                headers=auth_headers,
            )
            assert resp.status_code == 400, f"Expected 400 for id={malicious_id!r}"

    @pytest.mark.asyncio
    async def test_create_session_id_numeric_rejected(self, app_client, auth_headers):
        """Reject non-string id values."""
        resp = await app_client.post(
            "/sessions",
            json={"id": 12345},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_session_valid_uuid_accepted(self, app_client, auth_headers, mock_cosmos):
        """Accept a properly formatted UUID v4."""
        valid_id = str(uuid.uuid4())
        resp = await app_client.post(
            "/sessions",
            json={"id": valid_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title=None, session_id=valid_id)

    @pytest.mark.asyncio
    async def test_create_session_title_too_long(self, app_client, auth_headers):
        """Reject titles exceeding max length."""
        resp = await app_client.post(
            "/sessions",
            json={"title": "x" * 201},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = await resp.get_json()
        assert "Title too long" in data["error"]

    @pytest.mark.asyncio
    async def test_get_session_invalid_path_id(self, app_client, auth_headers):
        """Reject non-UUID session ID in URL path."""
        resp = await app_client.get("/sessions/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_messages_invalid_path_id(self, app_client, auth_headers):
        resp = await app_client.get("/sessions/not-a-uuid/messages", headers=auth_headers)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_invalid_path_id(self, app_client, auth_headers):
        resp = await app_client.post(
            "/sessions/not-a-uuid/messages",
            json={"content": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    # ── Duplicate / conflict ──

    @pytest.mark.asyncio
    async def test_create_session_duplicate_id_conflict(self, app_client, auth_headers, mock_cosmos):
        """Return 409 when client reuses an existing session ID."""
        from cosmos import SessionConflictError

        mock_cosmos.create_session.side_effect = SessionConflictError(TEST_SESSION_ID)

        resp = await app_client.post(
            "/sessions",
            json={"id": TEST_SESSION_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        data = await resp.get_json()
        assert "already exists" in data["error"]

    # ── Cross-user isolation ──

    @pytest.mark.asyncio
    async def test_cross_user_session_access_denied(self, app_client, mock_cosmos):
        """User B cannot access User A's session — get_session returns None for wrong partition."""
        import jwt as pyjwt

        # Create a JWT for User B
        now = datetime.datetime.now(datetime.timezone.utc)
        token_b = pyjwt.encode(
            {"sub": TEST_USER_ID_B, "email": TEST_USER_EMAIL_B, "iat": now, "exp": now + datetime.timedelta(hours=1)},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Cosmos returns None when partition key (userId) doesn't match
        mock_cosmos.get_session.return_value = None

        resp = await app_client.get(f"/sessions/{TEST_SESSION_ID}", headers=headers_b)
        assert resp.status_code == 404

        # Verify Cosmos was called with User B's ID (ownership enforcement via partition key)
        mock_cosmos.get_session.assert_called_with(TEST_USER_ID_B, TEST_SESSION_ID)

    @pytest.mark.asyncio
    async def test_cross_user_messages_denied(self, app_client, mock_cosmos):
        """User B cannot read User A's messages."""
        import jwt as pyjwt

        now = datetime.datetime.now(datetime.timezone.utc)
        token_b = pyjwt.encode(
            {"sub": TEST_USER_ID_B, "email": TEST_USER_EMAIL_B, "iat": now, "exp": now + datetime.timedelta(hours=1)},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}

        mock_cosmos.get_session.return_value = None

        resp = await app_client.get(f"/sessions/{TEST_SESSION_ID}/messages", headers=headers_b)
        assert resp.status_code == 404
        mock_cosmos.get_session.assert_called_with(TEST_USER_ID_B, TEST_SESSION_ID)

    @pytest.mark.asyncio
    async def test_cross_user_send_message_denied(self, app_client, mock_cosmos):
        """User B cannot send messages to User A's session."""
        import jwt as pyjwt

        now = datetime.datetime.now(datetime.timezone.utc)
        token_b = pyjwt.encode(
            {"sub": TEST_USER_ID_B, "email": TEST_USER_EMAIL_B, "iat": now, "exp": now + datetime.timedelta(hours=1)},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}

        mock_cosmos.get_session.return_value = None

        resp = await app_client.post(
            f"/sessions/{TEST_SESSION_ID}/messages",
            json={"content": "I am the attacker"},
            headers=headers_b,
        )
        assert resp.status_code == 404
        mock_cosmos.get_session.assert_called_with(TEST_USER_ID_B, TEST_SESSION_ID)

    @pytest.mark.asyncio
    async def test_cross_user_session_id_reuse_isolated(self, app_client, mock_cosmos):
        """
        User B creating a session with the same ID as User A's session
        should succeed (different partition key) — Cosmos isolates by userId.
        """
        import jwt as pyjwt

        now = datetime.datetime.now(datetime.timezone.utc)
        token_b = pyjwt.encode(
            {"sub": TEST_USER_ID_B, "email": TEST_USER_EMAIL_B, "iat": now, "exp": now + datetime.timedelta(hours=1)},
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Cosmos create_item succeeds because different partition key (userId)
        mock_cosmos.create_session.return_value = {
            "id": TEST_SESSION_ID,
            "type": "session",
            "userId": TEST_USER_ID_B,
            "status": "active",
            "createdAt": "2025-01-01T00:00:00+00:00",
        }

        resp = await app_client.post(
            "/sessions",
            json={"id": TEST_SESSION_ID},
            headers=headers_b,
        )
        assert resp.status_code == 201
        mock_cosmos.create_session.assert_called_once_with(
            TEST_USER_ID_B, title=None, session_id=TEST_SESSION_ID
        )
