"""
Cosmos DB clients ported from legacy/cosmos_db.py.

Provides:
- CosmosLeadGenClient: URL-keyed cache for lead/attorney scrape results
- CosmosBuyersClient: buyer lookup by city/state

Both are lazily initialized to tolerate missing env vars.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import certifi
except ImportError:
    certifi = None

try:
    from azure.cosmos.aio import CosmosClient
    from azure.cosmos import exceptions as cosmos_exceptions
except ImportError:
    CosmosClient = None
    cosmos_exceptions = None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


class CosmosLeadGenClient:
    """URL-keyed 24-hour cache for scraped lead/attorney data."""

    _instance: Optional[CosmosLeadGenClient] = None

    def __init__(self, endpoint: str, key: str, database: str, container: str):
        self.endpoint = endpoint
        self.key = key
        self.database_name = database
        self.container_name = container

    @classmethod
    def get_instance(cls) -> Optional[CosmosLeadGenClient]:
        if cls._instance is not None:
            return cls._instance

        account = _env("AZURE_COSMOSDB_ACCOUNT")
        key = _env("AZURE_COSMOSDB_ACCOUNT_KEY")
        db = _env("AZURE_COSMOSDB_LEADGEN_DATABASE")
        container = _env("AZURE_COSMOSDB_LEADGEN_CONTAINER")

        if not all([account, key, db, container]):
            logger.info("LeadGen Cosmos config incomplete; caching disabled.")
            return None

        if CosmosClient is None:
            logger.warning("azure-cosmos not installed; caching disabled.")
            return None

        if certifi:
            os.environ["SSL_CERT_FILE"] = certifi.where()

        cls._instance = cls(
            endpoint=f"https://{account}.documents.azure.com:443/",
            key=key,
            database=db,
            container=container,
        )
        return cls._instance

    async def get_cached_data(self, url: str) -> Optional[dict[str, Any]]:
        """Retrieve cached data if less than 24 hours old."""
        query = "SELECT * FROM c WHERE c.url = @url AND c.timestamp >= @timestamp"
        params = [
            {"name": "@url", "value": url},
            {"name": "@timestamp", "value": (datetime.utcnow() - timedelta(hours=24)).isoformat()},
        ]
        async with CosmosClient(self.endpoint, credential=self.key) as client:
            db = client.get_database_client(self.database_name)
            container = db.get_container_client(self.container_name)
            results = []
            async for item in container.query_items(query=query, parameters=params):
                results.append(item)
            return results[0] if results else None

    async def clear_cache(self, url: Optional[str] = None) -> int:
        """Delete cached lead entries. If url is given, delete only that URL's cache.
        Otherwise delete ALL cached entries. Returns count of deleted items."""
        if url:
            query = "SELECT c.id, c.url FROM c WHERE c.url = @url"
            params = [{"name": "@url", "value": url}]
        else:
            query = "SELECT c.id, c.url FROM c"
            params = []

        deleted = 0
        async with CosmosClient(self.endpoint, credential=self.key) as client:
            db = client.get_database_client(self.database_name)
            container = db.get_container_client(self.container_name)
            items = []
            async for item in container.query_items(query=query, parameters=params):
                items.append(item)
            for item in items:
                try:
                    await container.delete_item(item=item["id"], partition_key=item["id"])
                    deleted += 1
                except Exception:
                    logger.warning("Failed to delete cache item %s", item["id"])
        return deleted

    async def write_to_cache(self, url: str, data: dict[str, Any], timestamp: str) -> None:
        """Write scrape result to cache."""
        item = {
            "id": str(uuid.uuid4()),
            "url": url,
            "timestamp": timestamp,
            **data,
        }
        async with CosmosClient(self.endpoint, credential=self.key) as client:
            db = client.get_database_client(self.database_name)
            container = db.get_container_client(self.container_name)
            await container.upsert_item(item)


class CosmosBuyersClient:
    """Buyer lookup by city/state from Cosmos nationwide buyers container."""

    _instance: Optional[CosmosBuyersClient] = None

    def __init__(self, endpoint: str, key: str, database: str, container: str):
        self.endpoint = endpoint
        self.key = key
        self.database_name = database
        self.container_name = container

    @classmethod
    def get_instance(cls) -> Optional[CosmosBuyersClient]:
        if cls._instance is not None:
            return cls._instance

        account = _env("AZURE_COSMOSDB_ACCOUNT")
        key = _env("AZURE_COSMOSDB_ACCOUNT_KEY")
        db = _env("AZURE_COSMOSDB_BUYERS_DATABASE")
        container = _env("AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER")

        if not all([account, key, db, container]):
            logger.info("Buyers Cosmos config incomplete; buyers search disabled.")
            return None

        if CosmosClient is None:
            logger.warning("azure-cosmos not installed; buyers search disabled.")
            return None

        if certifi:
            os.environ["SSL_CERT_FILE"] = certifi.where()

        cls._instance = cls(
            endpoint=f"https://{account}.documents.azure.com:443/",
            key=key,
            database=db,
            container=container,
        )
        return cls._instance
