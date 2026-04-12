#!/usr/bin/env python3
"""
One-off: mark specific users as canceled in Cosmos DB.

Usage:
  python scripts/cancel-users.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_env_file = Path(__file__).parent.parent / "apps" / "api" / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

try:
    from azure.cosmos.aio import CosmosClient
except ImportError:
    sys.exit("azure-cosmos not installed. Run: pip install azure-cosmos")

# Users confirmed canceled (had Stripe customer record but no active plan)
CANCELED_EMAILS = [
    "webuyanyhousesusa@gmail.com",
    "ohio304@gmail.com",
    "juarezcourtney@gmail.com",
    "homesellusa@gmail.com",
    "d.oh.g@icloud.com",
    "4mario@gmail.com",
    "will@localbosshero.com",
    "giuseppe@romanempireinfrastructures.com",
]


async def main() -> None:
    account = (os.getenv("AZURE_COSMOSDB_ACCOUNT") or "").strip()
    key = (os.getenv("AZURE_COSMOSDB_ACCOUNT_KEY") or "").strip()
    database = (os.getenv("AZURE_COSMOSDB_DATABASE") or "db_conversation_history").strip()
    container_name = (os.getenv("AZURE_COSMOSDB_SESSIONS_CONTAINER") or "sessions").strip()

    if not account or not key:
        sys.exit("AZURE_COSMOSDB_ACCOUNT / AZURE_COSMOSDB_ACCOUNT_KEY not set")

    endpoint = f"https://{account}.documents.azure.com:443/"
    print(f"Connecting to: {account} / {database} / {container_name}\n")

    async with CosmosClient(endpoint, credential=key) as client:
        db = client.get_database_client(database)
        container = db.get_container_client(container_name)

        for email in CANCELED_EMAILS:
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
            params = [{"name": "@email", "value": email}]

            user_doc = None
            async for item in container.query_items(query=query, parameters=params):
                user_doc = item
                break

            if not user_doc:
                print(f"  SKIP  {email} — no ARI account found")
                continue

            current_status = user_doc.get("subscription_status", "")
            current_tier = user_doc.get("tier", "")

            if current_status == "canceled" and not current_tier:
                print(f"  OK    {email} — already canceled, skipping")
                continue

            user_doc["subscription_status"] = "canceled"
            user_doc["tier"] = ""
            user_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            await container.upsert_item(user_doc)
            print(f"  DONE  {email} — set subscription_status=canceled, tier='' (was: status={current_status!r}, tier={current_tier!r})")


if __name__ == "__main__":
    asyncio.run(main())
