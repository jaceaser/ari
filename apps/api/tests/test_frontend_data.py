"""Tests for frontend data persistence endpoints (PR9a)."""

import pytest
from unittest.mock import AsyncMock

from _constants import TEST_USER_ID


class TestFrontendDataAuth:
    @pytest.mark.asyncio
    async def test_data_endpoints_require_jwt(self, app_client):
        """All /data/* endpoints require JWT."""
        endpoints = [
            ("POST", "/data/messages"),
            ("GET", "/data/messages/msg-1"),
            ("POST", "/data/documents"),
            ("GET", "/data/documents/doc-1"),
            ("POST", "/data/suggestions"),
            ("GET", "/data/suggestions?documentId=doc-1&documentCreatedAt=0"),
            ("POST", "/data/votes"),
            ("GET", "/data/votes?chatId=chat-1"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = await app_client.get(path)
            else:
                resp = await app_client.post(path, json={})
            assert resp.status_code == 401, f"Expected 401 for {method} {path}, got {resp.status_code}"


class TestMessages:
    @pytest.mark.asyncio
    async def test_save_messages(self, app_client, auth_headers, mock_cosmos):
        """POST /data/messages saves messages."""
        mock_cosmos.save_messages = AsyncMock(return_value=[{"id": "m1"}])

        resp = await app_client.post(
            "/data/messages",
            json={"chatId": "c1", "messages": [
                {"id": "m1", "chatId": "c1", "role": "user", "parts": "[]", "attachments": "[]", "createdAt": 1000},
            ]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        mock_cosmos.save_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_message_by_id(self, app_client, auth_headers, mock_cosmos):
        """GET /data/messages/:id returns message."""
        mock_cosmos.get_message_by_id = AsyncMock(return_value={
            "id": "msg-1", "chatId": "c1", "role": "user",
        })

        resp = await app_client.get("/data/messages/msg-1", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["id"] == "msg-1"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, app_client, auth_headers, mock_cosmos):
        """GET /data/messages/:id returns 404 if not found."""
        mock_cosmos.get_message_by_id = AsyncMock(return_value=None)

        resp = await app_client.get("/data/messages/missing", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_message_count(self, app_client, auth_headers, mock_cosmos):
        """GET /data/messages/count?hours=24 returns count."""
        mock_cosmos.get_message_count = AsyncMock(return_value=42)

        resp = await app_client.get(
            "/data/messages/count?hours=24",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["count"] == 42


class TestDocuments:
    @pytest.mark.asyncio
    async def test_save_document(self, app_client, auth_headers, mock_cosmos):
        """POST /data/documents saves a document."""
        mock_cosmos.save_document = AsyncMock(return_value={
            "id": "doc-1", "title": "Test", "kind": "text", "content": "hello",
        })

        resp = await app_client.post(
            "/data/documents",
            json={
                "id": "doc-1",
                "title": "Test",
                "kind": "text",
                "content": "hello",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document(self, app_client, auth_headers, mock_cosmos):
        """GET /data/documents/:id returns document."""
        mock_cosmos.get_document_by_id = AsyncMock(return_value={
            "id": "doc-1", "title": "Test", "kind": "text",
        })

        resp = await app_client.get("/data/documents/doc-1", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_documents_by_id(self, app_client, auth_headers, mock_cosmos):
        """GET /data/documents/:id?all=true returns all versions."""
        mock_cosmos.get_documents_by_id = AsyncMock(return_value=[
            {"id": "doc-1", "title": "v1"},
            {"id": "doc-1", "title": "v2"},
        ])

        resp = await app_client.get(
            "/data/documents/doc-1?all=true",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = await resp.get_json()
        assert len(data) == 2


class TestVotes:
    @pytest.mark.asyncio
    async def test_vote_message(self, app_client, auth_headers, mock_cosmos):
        """POST /data/votes saves a vote."""
        mock_cosmos.vote_message = AsyncMock(return_value={
            "chatId": "c1", "messageId": "m1", "isUpvoted": 1,
        })

        resp = await app_client.post(
            "/data/votes",
            json={"chatId": "c1", "messageId": "m1", "type": "up"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_votes(self, app_client, auth_headers, mock_cosmos):
        """GET /data/votes?chatId=... returns votes."""
        mock_cosmos.get_votes_by_chat_id = AsyncMock(return_value=[
            {"chatId": "c1", "messageId": "m1", "isUpvoted": 1},
        ])

        resp = await app_client.get("/data/votes?chatId=c1", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert len(data) == 1


class TestSuggestions:
    @pytest.mark.asyncio
    async def test_save_suggestions(self, app_client, auth_headers, mock_cosmos):
        """POST /data/suggestions saves suggestions."""
        mock_cosmos.save_suggestions = AsyncMock(return_value=[{"id": "s1"}])

        resp = await app_client.post(
            "/data/suggestions",
            json={"suggestions": [
                {
                    "id": "s1",
                    "documentId": "doc-1",
                    "documentCreatedAt": 1000,
                    "originalText": "old",
                    "suggestedText": "new",
                    "userId": TEST_USER_ID,
                },
            ]},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_suggestions(self, app_client, auth_headers, mock_cosmos):
        """GET /data/suggestions returns suggestions for a document."""
        mock_cosmos.get_suggestions_by_document_id = AsyncMock(return_value=[
            {"id": "s1", "documentId": "doc-1"},
        ])

        resp = await app_client.get(
            "/data/suggestions?documentId=doc-1&documentCreatedAt=1000",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = await resp.get_json()
        assert len(data) == 1
