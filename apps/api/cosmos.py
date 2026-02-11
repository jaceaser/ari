"""
Azure Cosmos DB client for API persistence layer.

Container: 'sessions' in database 'db_conversation_history'
Partition key: userId
Document types: session, message, lead_run
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("api.cosmos")

try:
    from azure.cosmos.aio import CosmosClient
    from azure.cosmos import exceptions as cosmos_exceptions
except ImportError:
    CosmosClient = None  # type: ignore
    cosmos_exceptions = None  # type: ignore

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass


def _env(key: str) -> str:
    return (os.getenv(key) or "").strip()


class SessionsCosmosClient:
    """Async Cosmos DB client for sessions, messages, and lead runs."""

    _instance: Optional[SessionsCosmosClient] = None

    def __init__(self, endpoint: str, key: str, database: str, container: str):
        self.endpoint = endpoint
        self.key = key
        self.database_name = database
        self.container_name = container

    @classmethod
    def get_instance(cls) -> Optional[SessionsCosmosClient]:
        if cls._instance is not None:
            return cls._instance

        account = _env("AZURE_COSMOSDB_ACCOUNT")
        key = _env("AZURE_COSMOSDB_ACCOUNT_KEY")
        database = _env("AZURE_COSMOSDB_DATABASE") or "db_conversation_history"
        container = _env("AZURE_COSMOSDB_SESSIONS_CONTAINER") or "sessions"

        if not all([account, key]):
            logger.info("Cosmos config incomplete; persistence disabled.")
            return None

        if CosmosClient is None:
            logger.warning("azure-cosmos not installed; persistence disabled.")
            return None

        endpoint = f"https://{account}.documents.azure.com:443/"
        cls._instance = cls(endpoint, key, database, container)
        logger.info("Cosmos sessions client initialized: %s/%s", database, container)
        return cls._instance

    def _client(self):
        return CosmosClient(self.endpoint, credential=self.key)

    async def _container(self, client):
        db = client.get_database_client(self.database_name)
        return db.get_container_client(self.container_name)

    # ── Users ──

    async def ensure_user(self, user_id: str, email: str) -> dict[str, Any]:
        """Find or create user document. Returns user dict."""
        async with self._client() as client:
            container = await self._container(client)
            # Try to read existing user
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
            params = [{"name": "@email", "value": email}]
            items = []
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                items.append(item)

            if items:
                return items[0]

            # Create new user
            user_doc = {
                "id": user_id,
                "type": "user",
                "userId": user_id,
                "email": email,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            await container.upsert_item(user_doc)
            logger.info("Created new user: %s", email)
            return user_doc

    # ── Sessions ──

    async def create_session(self, user_id: str, title: Optional[str] = None) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        doc = {
            "id": session_id,
            "type": "session",
            "userId": user_id,
            "title": title,
            "status": "active",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sealedAt": None,
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        return doc

    async def get_sessions(self, user_id: str) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE c.type = 'session' AND c.userId = @userId "
            "ORDER BY c.createdAt DESC"
        )
        params = [{"name": "@userId", "value": user_id}]
        results = []
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                results.append(item)
        return results

    async def get_session(self, user_id: str, session_id: str) -> Optional[dict[str, Any]]:
        async with self._client() as client:
            container = await self._container(client)
            try:
                item = await container.read_item(item=session_id, partition_key=user_id)
                if item.get("type") != "session":
                    return None
                return item
            except Exception:
                return None

    async def seal_session(self, user_id: str, session_id: str) -> Optional[dict[str, Any]]:
        session = await self.get_session(user_id, session_id)
        if not session:
            return None
        session["status"] = "sealed"
        session["sealedAt"] = datetime.now(timezone.utc).isoformat()
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(session)
        return session

    # ── Messages ──

    async def create_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        msg_id = str(uuid.uuid4())
        doc = {
            "id": msg_id,
            "type": "message",
            "userId": user_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "metadata": metadata,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        return doc

    async def get_messages(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session (for UI replay). Ordered ASC."""
        query = (
            "SELECT * FROM c WHERE c.type = 'message' AND c.sessionId = @sessionId "
            "AND c.userId = @userId ORDER BY c.createdAt ASC"
        )
        params = [
            {"name": "@sessionId", "value": session_id},
            {"name": "@userId", "value": user_id},
        ]
        results = []
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                results.append(item)
        return results

    async def get_recent_messages(
        self, user_id: str, session_id: str, limit: int = 40
    ) -> list[dict[str, Any]]:
        """Get last N messages for LLM context windowing. Ordered ASC."""
        query = (
            "SELECT TOP @limit * FROM c WHERE c.type = 'message' "
            "AND c.sessionId = @sessionId AND c.userId = @userId "
            "ORDER BY c.createdAt DESC"
        )
        params = [
            {"name": "@limit", "value": limit},
            {"name": "@sessionId", "value": session_id},
            {"name": "@userId", "value": user_id},
        ]
        results = []
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                results.append(item)
        # Reverse to get chronological order
        results.reverse()
        return results

    # ── Lead Runs ──

    async def create_lead_run(
        self,
        user_id: str,
        session_id: Optional[str],
        summary: str,
        location: str,
        strategy: str,
        result_count: int,
        file_url: str,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        doc = {
            "id": run_id,
            "type": "lead_run",
            "userId": user_id,
            "sessionId": session_id,
            "summary": summary,
            "location": location,
            "strategy": strategy,
            "resultCount": result_count,
            "filters": filters,
            "fileUrl": file_url,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        # Log without file_url for security
        logger.info("Created lead run %s for user %s (%d results)", run_id, user_id, result_count)
        return doc

    async def get_lead_runs(self, user_id: str) -> list[dict[str, Any]]:
        query = (
            "SELECT c.id, c.summary, c.location, c.strategy, c.resultCount, c.createdAt "
            "FROM c WHERE c.type = 'lead_run' AND c.userId = @userId "
            "ORDER BY c.createdAt DESC"
        )
        params = [{"name": "@userId", "value": user_id}]
        results = []
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                results.append(item)
        return results

    async def get_lead_run(self, user_id: str, lead_run_id: str) -> Optional[dict[str, Any]]:
        async with self._client() as client:
            container = await self._container(client)
            try:
                item = await container.read_item(item=lead_run_id, partition_key=user_id)
                if item.get("type") != "lead_run":
                    return None
                return item
            except Exception:
                return None
