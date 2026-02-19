#!/usr/bin/env python3
"""
One-time migration: copy all subscription data from Redis to Cosmos DB.

Usage:
    pip install redis azure-cosmos aiohttp certifi
    python scripts/migrate_redis_to_cosmos.py

Environment variables (or edit the constants below):
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
    AZURE_COSMOSDB_ACCOUNT, AZURE_COSMOSDB_ACCOUNT_KEY
    AZURE_COSMOSDB_DATABASE, AZURE_COSMOSDB_SESSIONS_CONTAINER
"""

import asyncio
import json
import os
import ssl
import uuid
from datetime import datetime, timezone

import certifi
import redis

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# ── Config (override via env vars) ──
REDIS_HOST = os.getenv("REDIS_HOST", "ari-production.redis.cache.windows.net")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

COSMOS_ACCOUNT = os.getenv("AZURE_COSMOSDB_ACCOUNT", "db-uc-ai")
COSMOS_KEY = os.getenv("AZURE_COSMOSDB_ACCOUNT_KEY", "")
COSMOS_DB = os.getenv("AZURE_COSMOSDB_DATABASE", "db_conversation_history")
COSMOS_CONTAINER = os.getenv("AZURE_COSMOSDB_SESSIONS_CONTAINER", "sessions")
COSMOS_ENDPOINT = f"https://{COSMOS_ACCOUNT}.documents.azure.com:443/"


def derive_user_id(email: str) -> str:
    """Deterministic UUID5 matching the API's magic_link.py derivation."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))


async def main():
    from azure.cosmos.aio import CosmosClient

    # 1. Read all subscription:email keys from Redis
    rclient = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
        ssl=True, ssl_cert_reqs=ssl.CERT_NONE, ssl_check_hostname=False,
        decode_responses=True, socket_timeout=10, socket_connect_timeout=10, db=0,
    )

    keys = [k for k in rclient.keys("subscription:*") if not k.startswith("subscription_id:")]
    print(f"Found {len(keys)} subscription records in Redis")

    subs = []
    for k in sorted(keys):
        val = rclient.get(k)
        if val:
            subs.append(json.loads(val))
    rclient.close()

    # 2. Upsert into Cosmos
    async with CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY) as client:
        db = client.get_database_client(COSMOS_DB)
        container = db.get_container_client(COSMOS_CONTAINER)

        migrated = skipped = created_users = errors = 0

        for sub in subs:
            email = sub.get("user_email", "").strip().lower()
            if not email:
                continue

            user_id = derive_user_id(email)
            status = sub.get("status", "")
            plan = sub.get("plan_type", "")
            sub_id = sub.get("subscription_id")
            active_statuses = {"active", "pending", "trialing"}

            try:
                # Check for existing user doc
                query = "SELECT * FROM c WHERE c.type = 'user' AND c.userId = @uid"
                params = [{"name": "@uid", "value": user_id}]
                items = []
                async for item in container.query_items(
                    query=query, parameters=params, partition_key=user_id
                ):
                    items.append(item)

                if items:
                    doc = items[0]
                    if doc.get("subscription_status") and doc.get("legacy_redis_migrated"):
                        print(f"  SKIP {email}: already migrated")
                        skipped += 1
                        continue
                else:
                    doc = {
                        "id": user_id,
                        "type": "user",
                        "userId": user_id,
                        "email": email,
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                    }
                    created_users += 1

                doc.update({
                    "subscription_status": "active" if status in active_statuses else status,
                    "subscription_id": sub_id if sub_id and sub_id not in ("None", "") else None,
                    "plan": plan if plan != "unknown" else None,
                    "subscription_expires_at": sub.get("next_payment"),
                    "legacy_redis_migrated": True,
                    "redis_migration_date": datetime.now(timezone.utc).isoformat(),
                    "redis_original_status": status,
                    "redis_original_plan": plan,
                })

                await container.upsert_item(doc)
                print(f"  OK   {email}: status={status}->{doc['subscription_status']}, plan={plan}")
                migrated += 1

            except Exception as e:
                print(f"  ERR  {email}: {e}")
                errors += 1

    print(f"\nDone! Migrated: {migrated}, Skipped: {skipped}, New users: {created_users}, Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
