#!/usr/bin/env python3
"""
Audit all user accounts for subscription/tier mismatches.

Reports:
  - Users with stripe_customer_id but no tier (Stripe subscriber, tier not written)
  - Users with subscription_status=active but no tier
  - Users with no tier at all (free accounts)
  - Signup date for a specific email

Usage:
  python scripts/audit-user-tiers.py
  python scripts/audit-user-tiers.py --email 10xresourcesinc@gmail.com
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

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


async def main(email_filter: str | None) -> None:
    account = _env("AZURE_COSMOSDB_ACCOUNT")
    key = _env("AZURE_COSMOSDB_ACCOUNT_KEY")
    database = _env("AZURE_COSMOSDB_DATABASE") or "db_conversation_history"
    container_name = _env("AZURE_COSMOSDB_SESSIONS_CONTAINER") or "sessions"

    if not account or not key:
        sys.exit("AZURE_COSMOSDB_ACCOUNT / AZURE_COSMOSDB_ACCOUNT_KEY not set")

    endpoint = f"https://{account}.documents.azure.com:443/"
    print(f"Connecting to: {account} / {database} / {container_name}\n")

    async with CosmosClient(endpoint, credential=key) as client:
        db = client.get_database_client(database)
        container = db.get_container_client(container_name)

        if email_filter:
            # Single user lookup
            query = "SELECT * FROM c WHERE c.type = 'user' AND c.email = @email"
            params = [{"name": "@email", "value": email_filter}]
            async for item in container.query_items(query=query, parameters=params):
                print(f"Email:               {item.get('email')}")
                print(f"userId:              {item.get('userId') or item.get('id')}")
                print(f"Signed up:           {item.get('createdAt') or item.get('created_at') or '(no date field)'}")
                print(f"tier:                {item.get('tier')!r}")
                print(f"plan:                {item.get('plan')!r}")
                print(f"subscription_status: {item.get('subscription_status')!r}")
                print(f"stripe_customer_id:  {item.get('stripe_customer_id')!r}")
                print(f"apple_product_id:    {item.get('apple_product_id')!r}")
                print(f"updated_at:          {item.get('updated_at')!r}")
            return

        # Full audit
        query = "SELECT * FROM c WHERE c.type = 'user'"

        total = 0
        stripe_no_tier = []       # Has stripe_customer_id but tier is missing/free
        active_no_tier = []       # subscription_status=active but tier is missing/free
        no_sub_data = []          # No stripe, no apple, no tier — pure free accounts
        has_tier = []             # Properly tiered users

        async for item in container.query_items(query=query):
            total += 1
            email = item.get("email", "(no email)")
            user_id = item.get("userId") or item.get("id", "")
            tier = (item.get("tier") or "").strip().lower()
            plan = (item.get("plan") or "").strip().lower()
            status = (item.get("status") or item.get("subscription_status") or "").strip().lower()
            stripe_id = item.get("stripe_customer_id") or ""
            apple_id = item.get("apple_product_id") or ""
            created = item.get("createdAt") or item.get("created_at") or ""
            updated = item.get("updated_at") or ""

            normalized_tier = tier
            _plan_map = {
                "ari_elite": "elite", "ari_pro": "elite", "ari_lite": "lite",
                "elite": "elite", "pro": "elite", "lite": "lite", "basic": "lite",
            }
            if normalized_tier not in ("elite", "lite"):
                normalized_tier = _plan_map.get(plan, "")

            entry = {
                "email": email,
                "userId": user_id,
                "tier": tier or "(none)",
                "plan": plan or "(none)",
                "status": status or "(none)",
                "stripe_customer_id": stripe_id or "(none)",
                "apple_product_id": apple_id or "(none)",
                "created": created or "(none)",
                "updated": updated or "(none)",
            }

            if normalized_tier in ("elite", "lite"):
                has_tier.append(entry)
            elif stripe_id and status == "active":
                stripe_no_tier.append(entry)
            elif stripe_id:
                stripe_no_tier.append(entry)
            elif apple_id:
                active_no_tier.append(entry)
            elif status == "active":
                active_no_tier.append(entry)
            else:
                no_sub_data.append(entry)

        print(f"Total user accounts: {total}")
        print(f"  Properly tiered:         {len(has_tier)}")
        print(f"  Stripe linked, no tier:  {len(stripe_no_tier)}  ← likely billing bug")
        print(f"  Active status, no tier:  {len(active_no_tier)}  ← possible billing bug")
        print(f"  Pure free (no sub data): {len(no_sub_data)}")
        print()

        if stripe_no_tier:
            print("=== STRIPE LINKED BUT NO TIER (likely billing bug) ===")
            for u in stripe_no_tier:
                print(f"  {u['email']:<40}  stripe={u['stripe_customer_id'][:20]}  status={u['status']}  created={u['created']}")
            print()

        if active_no_tier:
            print("=== ACTIVE STATUS BUT NO TIER ===")
            for u in active_no_tier:
                print(f"  {u['email']:<40}  apple={u['apple_product_id']}  status={u['status']}  created={u['created']}")
            print()

        if has_tier:
            print("=== TIERED USERS ===")
            for u in has_tier:
                print(f"  {u['email']:<40}  tier={u['tier']}  plan={u['plan']}  status={u['status']}  created={u['created']}")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", help="Look up a single user by email")
    args = parser.parse_args()
    asyncio.run(main(args.email))
