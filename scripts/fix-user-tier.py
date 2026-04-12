#!/usr/bin/env python3
"""
One-off script: look up a user by email and show/fix their subscription tier in Cosmos DB.

Usage:
  # Show current state:
  python scripts/fix-user-tier.py 10xresourcesinc@gmail.com

  # Set tier to elite:
  python scripts/fix-user-tier.py 10xresourcesinc@gmail.com --set-tier elite

  # Set tier to lite:
  python scripts/fix-user-tier.py 10xresourcesinc@gmail.com --set-tier lite

Reads AZURE_COSMOSDB_ACCOUNT and AZURE_COSMOSDB_ACCOUNT_KEY from apps/api/.env
(or from env vars if already set).
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env from apps/api if not already set
_env_file = Path(__file__).parent.parent / "apps" / "api" / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

try:
    from azure.cosmos.aio import CosmosClient
except ImportError:
    sys.exit("azure-cosmos not installed. Run: pip install azure-cosmos")


def _env(key: str) -> str:
    return (os.getenv(key) or "").strip()


async def main(email: str, set_tier: str | None) -> None:
    account = _env("AZURE_COSMOSDB_ACCOUNT")
    key = _env("AZURE_COSMOSDB_ACCOUNT_KEY")
    database = _env("AZURE_COSMOSDB_DATABASE") or "db_conversation_history"
    container_name = _env("AZURE_COSMOSDB_SESSIONS_CONTAINER") or "sessions"

    if not account or not key:
        sys.exit("AZURE_COSMOSDB_ACCOUNT / AZURE_COSMOSDB_ACCOUNT_KEY not set")

    endpoint = f"https://{account}.documents.azure.com:443/"
    print(f"Connecting to: {account} / {database} / {container_name}")

    async with CosmosClient(endpoint, credential=key) as client:
        db = client.get_database_client(database)
        container = db.get_container_client(container_name)

        query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
        params = [{"name": "@email", "value": email}]

        user_doc = None
        async for item in container.query_items(query=query, parameters=params):
            user_doc = item
            break

        if not user_doc:
            print(f"ERROR: No user found for email: {email}")
            sys.exit(1)

        user_id = user_doc.get("userId") or user_doc.get("id")
        print(f"\nUser found:")
        print(f"  userId:              {user_id}")
        print(f"  email:               {user_doc.get('email')}")
        print(f"  tier:                {user_doc.get('tier')!r}")
        print(f"  plan:                {user_doc.get('plan')!r}")
        print(f"  subscription_status: {user_doc.get('subscription_status')!r}")
        print(f"  stripe_customer_id:  {user_doc.get('stripe_customer_id')!r}")
        print(f"  apple_product_id:    {user_doc.get('apple_product_id')!r}")
        print(f"  updated_at:          {user_doc.get('updated_at')!r}")

        if set_tier:
            if set_tier not in ("free", "lite", "elite"):
                sys.exit(f"Invalid tier: {set_tier!r}. Must be free, lite, or elite.")

            _default_plan = {"lite": "ari_lite", "elite": "ari_elite", "free": ""}
            user_doc["tier"] = set_tier
            if set_tier != "free" and not user_doc.get("plan"):
                user_doc["plan"] = _default_plan[set_tier]
            user_doc["subscription_status"] = "active" if set_tier != "free" else user_doc.get("subscription_status")
            user_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            await container.upsert_item(user_doc)
            print(f"\nOK: tier set to {set_tier!r} for {email}")
        else:
            print("\n(dry run — pass --set-tier to make changes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect/fix user tier in Cosmos DB")
    parser.add_argument("email", help="User email address")
    parser.add_argument("--set-tier", choices=["free", "lite", "elite"], help="New tier to assign")
    args = parser.parse_args()

    asyncio.run(main(args.email, args.set_tier))
