#!/usr/bin/env python3
"""
One-off: apply a checkout.session.completed payload directly to a user's Cosmos record,
and remove the stale idempotency entry so future events process correctly.

Usage:
  python scripts/apply-stripe-checkout.py
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
    sys.exit("azure-cosmos not installed.")

ACCOUNT  = (os.getenv("AZURE_COSMOSDB_ACCOUNT") or "").strip()
KEY      = (os.getenv("AZURE_COSMOSDB_ACCOUNT_KEY") or "").strip()
DATABASE = (os.getenv("AZURE_COSMOSDB_DATABASE") or "db_conversation_history").strip()
CONTAINER = (os.getenv("AZURE_COSMOSDB_SESSIONS_CONTAINER") or "sessions").strip()

# ── Data from the Stripe payload ─────────────────────────────────────────────
EMAIL           = "10xresourcesinc@gmail.com"
STRIPE_CUSTOMER = "cus_UHdkZCFsSkUwM6"
SUBSCRIPTION_ID = "sub_1TJ4SgA8LlrWRNKgntmVAnLd"
EVENT_ID        = "evt_1TJ4SiA8LlrWRNKgmDA7h4kc"
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    if not ACCOUNT or not KEY:
        sys.exit("AZURE_COSMOSDB_ACCOUNT / AZURE_COSMOSDB_ACCOUNT_KEY not set")

    endpoint = f"https://{ACCOUNT}.documents.azure.com:443/"
    async with CosmosClient(endpoint, credential=KEY) as client:
        db = client.get_database_client(DATABASE)
        container = db.get_container_client(CONTAINER)

        # 1. Find user by email
        query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
        user_doc = None
        async for item in container.query_items(query=query, parameters=[{"name": "@email", "value": EMAIL}]):
            user_doc = item
            break

        if not user_doc:
            sys.exit(f"No user found for {EMAIL}")

        # 2. Apply Stripe data
        user_doc["stripe_customer_id"] = STRIPE_CUSTOMER
        user_doc["subscription_id"]    = SUBSCRIPTION_ID
        user_doc["subscription_status"] = "active"
        user_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await container.upsert_item(user_doc)
        print(f"✓ Updated user {EMAIL} with stripe_customer_id={STRIPE_CUSTOMER}")

        # 3. Delete the stale idempotency record so future events process correctly
        try:
            await container.delete_item(item=EVENT_ID, partition_key="system")
            print(f"✓ Deleted idempotency record for {EVENT_ID}")
        except Exception:
            print(f"  (idempotency record already gone or not found — that's fine)")

        # 4. Show final state
        async for item in container.query_items(query=query, parameters=[{"name": "@email", "value": EMAIL}]):
            print(f"\nFinal state:")
            print(f"  tier:                {item.get('tier')!r}")
            print(f"  plan:                {item.get('plan')!r}")
            print(f"  subscription_status: {item.get('subscription_status')!r}")
            print(f"  stripe_customer_id:  {item.get('stripe_customer_id')!r}")
            print(f"  subscription_id:     {item.get('subscription_id')!r}")
            break


asyncio.run(main())
