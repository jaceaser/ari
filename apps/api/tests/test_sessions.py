"""Tests for session CRUD and message endpoints."""

import pytest

from _constants import TEST_USER_ID


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.post("/sessions", headers=auth_headers)
        assert resp.status_code == 201
        data = await resp.get_json()
        assert "id" in data
        assert "created_at" in data
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title=None)

    @pytest.mark.asyncio
    async def test_create_session_with_title(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.post(
            "/sessions",
            json={"title": "My Session"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        mock_cosmos.create_session.assert_called_once_with(TEST_USER_ID, title="My Session")

    @pytest.mark.asyncio
    async def test_list_sessions(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get("/sessions", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "sess-123"
        assert data[0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_session(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get("/sessions/sess-123", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["id"] == "sess-123"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        resp = await app_client.get("/sessions/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_seal_session(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.post("/sessions/sess-123/seal", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["status"] == "sealed"
        assert data["sealed_at"] is not None

    @pytest.mark.asyncio
    async def test_seal_nonexistent_session(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.seal_session.return_value = None
        resp = await app_client.post("/sessions/nonexistent/seal", headers=auth_headers)
        assert resp.status_code == 404


class TestMessages:
    @pytest.mark.asyncio
    async def test_list_messages(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get("/sessions/sess-123/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_list_messages_session_not_found(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        resp = await app_client.get("/sessions/nonexistent/messages", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_missing_content(self, app_client, auth_headers):
        resp = await app_client.post(
            "/sessions/sess-123/messages",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, app_client, auth_headers):
        resp = await app_client.post(
            "/sessions/sess-123/messages",
            json={"content": "  "},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_to_sealed_session(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = {
            "id": "sess-123",
            "status": "sealed",
            "userId": TEST_USER_ID,
        }
        resp = await app_client.post(
            "/sessions/sess-123/messages",
            json={"content": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_session(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_session.return_value = None
        resp = await app_client.post(
            "/sessions/nonexistent/messages",
            json={"content": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
