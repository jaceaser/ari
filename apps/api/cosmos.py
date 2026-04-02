"""
Azure Cosmos DB client for API persistence layer.

Container: 'sessions' in database 'db_conversation_history'
Partition key: userId
Document types: session, message, lead_run, document, suggestion, vote, magic_token
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
    from azure.cosmos import PartitionKey
except ImportError:
    CosmosClient = None  # type: ignore
    cosmos_exceptions = None  # type: ignore
    PartitionKey = None  # type: ignore

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass


class SessionConflictError(Exception):
    """Raised when a session with the given ID already exists."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session {session_id} already exists")


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
        self._container_verified = False

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
        if not self._container_verified:
            try:
                await db.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path="/userId"),
                )
                self._container_verified = True
                logger.info("Cosmos container '%s' verified/created", self.container_name)
            except Exception:
                # If we can't auto-create, proceed anyway — the container may already exist
                self._container_verified = True
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

    async def create_session(self, user_id: str, title: Optional[str] = None, session_id: Optional[str] = None) -> dict[str, Any]:
        """Create a session. Raises SessionConflictError if session_id already exists for this user."""
        session_id = session_id or str(uuid.uuid4())
        doc = {
            "id": session_id,
            "type": "session",
            "userId": user_id,
            "title": title,
            "status": "active",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        async with self._client() as client:
            container = await self._container(client)
            try:
                await container.create_item(doc)
            except Exception as exc:
                # Cosmos returns 409 Conflict when document with same id+partition already exists
                if cosmos_exceptions and isinstance(exc, cosmos_exceptions.CosmosResourceExistsError):
                    raise SessionConflictError(session_id) from exc
                raise
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

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session and all its messages."""
        async with self._client() as client:
            container = await self._container(client)
            # Delete all documents for this session (session + messages)
            query = "SELECT c.id FROM c WHERE c.userId = @uid AND c.sessionId = @sid"
            params = [
                {"name": "@uid", "value": user_id},
                {"name": "@sid", "value": session_id},
            ]
            items = [item async for item in container.query_items(query, parameters=params)]
            # Also include the session document itself
            items.append({"id": session_id})
            for item in items:
                try:
                    await container.delete_item(item=item["id"], partition_key=user_id)
                except Exception:
                    pass  # Already deleted or not found
        return True

    async def update_session(self, user_id: str, session: dict[str, Any]) -> dict[str, Any]:
        """Update an existing session document (e.g. title)."""
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
        source_url: str = "",
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
            "sourceUrl": source_url,
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

    # ── Frontend data: Messages (extended) ──

    async def save_messages(
        self, user_id: str, session_id: str, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Batch-save messages (parts-based format from frontend)."""
        saved = []
        async with self._client() as client:
            container = await self._container(client)
            for msg in messages:
                doc = {
                    "id": msg.get("id") or str(uuid.uuid4()),
                    "type": "message",
                    "userId": user_id,
                    "sessionId": session_id,
                    "role": msg.get("role", "user"),
                    "content": msg.get("parts", ""),
                    "parts": msg.get("parts", ""),
                    "attachments": msg.get("attachments", "[]"),
                    "createdAt": msg.get("createdAt") or datetime.now(timezone.utc).isoformat(),
                }
                await container.upsert_item(doc)
                saved.append(doc)
        return saved

    async def get_message_by_id(self, user_id: str, message_id: str) -> Optional[dict[str, Any]]:
        """Get a single message by ID."""
        query = "SELECT * FROM c WHERE c.type = 'message' AND c.id = @id AND c.userId = @userId"
        params = [
            {"name": "@id", "value": message_id},
            {"name": "@userId", "value": user_id},
        ]
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                return item
        return None

    async def update_message(
        self, user_id: str, message_id: str, updates: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Update a message's fields (e.g. parts)."""
        msg = await self.get_message_by_id(user_id, message_id)
        if not msg:
            return None
        msg.update(updates)
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(msg)
        return msg

    async def delete_messages_after_timestamp(
        self, user_id: str, session_id: str, timestamp: Any
    ) -> int:
        """Delete messages in a session created at or after the given timestamp."""
        query = (
            "SELECT c.id FROM c WHERE c.type = 'message' "
            "AND c.sessionId = @sessionId AND c.userId = @userId "
            "AND c.createdAt >= @ts"
        )
        params = [
            {"name": "@sessionId", "value": session_id},
            {"name": "@userId", "value": user_id},
            {"name": "@ts", "value": str(timestamp) if isinstance(timestamp, (int, float)) else timestamp},
        ]
        deleted = 0
        async with self._client() as client:
            container = await self._container(client)
            items = [
                item async for item in container.query_items(
                    query=query, parameters=params, partition_key=user_id
                )
            ]
            for item in items:
                try:
                    await container.delete_item(item=item["id"], partition_key=user_id)
                    deleted += 1
                except Exception:
                    pass
        return deleted

    async def get_message_count(
        self, user_id: str, since_hours: int = 24
    ) -> int:
        """Count user messages in the last N hours."""
        cutoff = datetime.now(timezone.utc).timestamp() - (since_hours * 3600)
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
        query = (
            "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'message' "
            "AND c.userId = @userId AND c.role = 'user' "
            "AND c.createdAt >= @cutoff"
        )
        params = [
            {"name": "@userId", "value": user_id},
            {"name": "@cutoff", "value": cutoff_iso},
        ]
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                return item
        return 0

    async def get_user_prompt_count_since(self, user_id: str, since_iso: str) -> int:
        """Count user-role prompt messages since a specific ISO timestamp."""
        query = (
            "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'message' "
            "AND c.userId = @userId AND c.role = 'user' "
            "AND c.createdAt >= @since"
        )
        params = [
            {"name": "@userId", "value": user_id},
            {"name": "@since", "value": since_iso},
        ]
        async with self._client() as client:
            container = await self._container(client)
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                return int(item or 0)
        return 0

    # ── Documents ──

    async def save_document(
        self, user_id: str, doc_id: str, title: str, kind: str,
        content: Optional[str] = None,
    ) -> dict[str, Any]:
        """Save a document version."""
        now = datetime.now(timezone.utc).isoformat()
        # Use composite key: doc_id + createdAt for versioning
        cosmos_id = f"doc:{doc_id}:{now}"
        doc = {
            "id": cosmos_id,
            "type": "document",
            "documentId": doc_id,
            "userId": user_id,
            "title": title,
            "kind": kind,
            "content": content,
            "createdAt": now,
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        return doc

    async def get_documents_by_id(self, user_id: str, doc_id: str) -> list[dict[str, Any]]:
        """Get all versions of a document, ordered by createdAt ASC."""
        query = (
            "SELECT * FROM c WHERE c.type = 'document' AND c.documentId = @docId "
            "AND c.userId = @userId ORDER BY c.createdAt ASC"
        )
        params = [
            {"name": "@docId", "value": doc_id},
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

    async def get_document_by_id(self, user_id: str, doc_id: str) -> Optional[dict[str, Any]]:
        """Get the latest version of a document."""
        docs = await self.get_documents_by_id(user_id, doc_id)
        return docs[-1] if docs else None

    async def delete_documents_after_timestamp(
        self, user_id: str, doc_id: str, timestamp: Any
    ) -> list[dict[str, Any]]:
        """Delete document versions created after the given timestamp."""
        query = (
            "SELECT * FROM c WHERE c.type = 'document' AND c.documentId = @docId "
            "AND c.userId = @userId AND c.createdAt > @ts"
        )
        params = [
            {"name": "@docId", "value": doc_id},
            {"name": "@userId", "value": user_id},
            {"name": "@ts", "value": str(timestamp) if isinstance(timestamp, (int, float)) else timestamp},
        ]
        deleted = []
        async with self._client() as client:
            container = await self._container(client)
            items = [
                item async for item in container.query_items(
                    query=query, parameters=params, partition_key=user_id
                )
            ]
            for item in items:
                try:
                    await container.delete_item(item=item["id"], partition_key=user_id)
                    deleted.append(item)
                except Exception:
                    pass
        return deleted

    # ── Suggestions ──

    async def save_suggestions(
        self, user_id: str, suggestions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Save suggestion documents."""
        saved = []
        async with self._client() as client:
            container = await self._container(client)
            for s in suggestions:
                doc = {
                    "id": s.get("id") or str(uuid.uuid4()),
                    "type": "suggestion",
                    "userId": user_id,
                    "documentId": s.get("documentId"),
                    "documentCreatedAt": s.get("documentCreatedAt"),
                    "originalText": s.get("originalText"),
                    "suggestedText": s.get("suggestedText"),
                    "description": s.get("description"),
                    "isResolved": s.get("isResolved", 0),
                    "createdAt": s.get("createdAt") or datetime.now(timezone.utc).isoformat(),
                }
                await container.upsert_item(doc)
                saved.append(doc)
        return saved

    async def get_suggestions_by_document_id(
        self, user_id: str, document_id: str
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE c.type = 'suggestion' AND c.documentId = @docId "
            "AND c.userId = @userId"
        )
        params = [
            {"name": "@docId", "value": document_id},
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

    # ── Votes ──

    async def vote_message(
        self, user_id: str, chat_id: str, message_id: str, is_upvoted: int
    ) -> dict[str, Any]:
        """Create or update a vote on a message."""
        vote_id = f"vote:{chat_id}:{message_id}"
        doc = {
            "id": vote_id,
            "type": "vote",
            "userId": user_id,
            "chatId": chat_id,
            "messageId": message_id,
            "isUpvoted": is_upvoted,
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        return doc

    async def get_votes_by_chat_id(
        self, user_id: str, chat_id: str
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE c.type = 'vote' AND c.chatId = @chatId "
            "AND c.userId = @userId"
        )
        params = [
            {"name": "@chatId", "value": chat_id},
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

    # ── Magic Tokens ──

    async def store_magic_token(
        self, email: str, token: str, expires_at: str
    ) -> dict[str, Any]:
        """Store a magic link token. Partition: userId='system'."""
        doc = {
            "id": token,
            "type": "magic_token",
            "userId": "system",
            "email": email,
            "expiresAt": expires_at,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
        return doc

    async def get_magic_token_raw(self, token: str) -> Optional[dict[str, Any]]:
        """Return the raw magic token doc regardless of expiry — for audit logging only."""
        async with self._client() as client:
            container = await self._container(client)
            try:
                item = await container.read_item(item=token, partition_key="system")
                if item.get("type") != "magic_token":
                    return None
                return item
            except Exception:
                return None

    async def verify_magic_token(self, token: str) -> Optional[dict[str, Any]]:
        """Look up a magic token. Returns the doc if found and not expired."""
        async with self._client() as client:
            container = await self._container(client)
            try:
                item = await container.read_item(item=token, partition_key="system")
                if item.get("type") != "magic_token":
                    return None
                # Check expiry
                expires_at = item.get("expiresAt", "")
                if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                    # Expired — clean up
                    await container.delete_item(item=token, partition_key="system")
                    return None
                return item
            except Exception:
                return None

    async def delete_magic_token(self, token: str) -> None:
        """Delete a magic token (single-use)."""
        async with self._client() as client:
            container = await self._container(client)
            try:
                await container.delete_item(item=token, partition_key="system")
            except Exception:
                pass

    # ── Subscriptions (Stripe) ──

    async def update_user_subscription(
        self, user_id: str, stripe_data: dict[str, Any]
    ) -> None:
        """Update a user document with Stripe subscription data."""
        async with self._client() as client:
            container = await self._container(client)
            # Find user doc
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.userId = @uid"
            params = [{"name": "@uid", "value": user_id}]
            items = []
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                items.append(item)

            if items:
                doc = items[0]
                doc.update(stripe_data)
                doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                await container.upsert_item(doc)
            else:
                logger.warning("No user doc found for %s to update subscription", user_id)

    async def get_user_subscription(self, user_id: str) -> Optional[dict[str, Any]]:
        """Get subscription info from a user document."""
        async with self._client() as client:
            container = await self._container(client)
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.userId = @uid"
            params = [{"name": "@uid", "value": user_id}]
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                return {
                    "subscription_status": item.get("subscription_status"),
                    "subscription_id": item.get("subscription_id"),
                    "stripe_customer_id": item.get("stripe_customer_id"),
                    "plan": item.get("plan"),
                    "subscription_expires_at": item.get("subscription_expires_at"),
                    "tier": item.get("tier"),
                    "updated_at": item.get("updated_at"),
                }
            return None

    async def update_user_email(self, user_id: str, new_email: str) -> None:
        """Update a user's email address."""
        async with self._client() as client:
            container = await self._container(client)
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.userId = @uid"
            params = [{"name": "@uid", "value": user_id}]
            async for item in container.query_items(
                query=query, parameters=params, partition_key=user_id
            ):
                item["email"] = new_email
                await container.upsert_item(item)
                return
            logger.warning("No user doc found for %s to update email", user_id)

    async def find_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Find a user document by email (cross-partition query)."""
        async with self._client() as client:
            container = await self._container(client)
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
            params = [{"name": "@email", "value": email}]
            async for item in container.query_items(
                query=query, parameters=params
            ):
                return item
            return None

    async def find_user_by_stripe_customer(self, customer_id: str) -> Optional[dict[str, Any]]:
        """Find a user document by Stripe customer ID (cross-partition query)."""
        async with self._client() as client:
            container = await self._container(client)
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.stripe_customer_id = @cid"
            params = [{"name": "@cid", "value": customer_id}]
            async for item in container.query_items(
                query=query, parameters=params
            ):
                return item
            return None

    async def find_user_by_subscription_id(self, subscription_id: str) -> Optional[dict[str, Any]]:
        """Find a user document by Stripe subscription ID (cross-partition query).

        Fallback for users whose stripe_customer_id was never written (e.g. migrated
        from Redis with partial data), so webhook events can still be matched.
        """
        async with self._client() as client:
            container = await self._container(client)
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.subscription_id = @sid"
            params = [{"name": "@sid", "value": subscription_id}]
            async for item in container.query_items(
                query=query, parameters=params
            ):
                return item
            return None

    # ── Stripe Idempotency ──

    async def has_stripe_event_been_processed(self, event_id: str) -> bool:
        """Return True if we have already processed this Stripe event ID."""
        async with self._client() as client:
            container = await self._container(client)
            try:
                item = await container.read_item(item=event_id, partition_key="system")
                return item.get("type") == "stripe_event"
            except Exception:
                return False

    async def record_stripe_event(self, event_id: str, event_type: str) -> None:
        """Mark a Stripe event ID as processed. Partition: userId='system'."""
        doc = {
            "id": event_id,
            "type": "stripe_event",
            "userId": "system",
            "eventType": event_type,
            "processedAt": datetime.now(timezone.utc).isoformat(),
        }
        async with self._client() as client:
            container = await self._container(client)
            await container.upsert_item(doc)
