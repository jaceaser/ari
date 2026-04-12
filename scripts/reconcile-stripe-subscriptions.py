#!/usr/bin/env python3
"""
Reconcile Stripe subscriptions against Cosmos DB.

For every tiered ARI user missing a stripe_customer_id, look them up in
Stripe by email and backfill stripe_customer_id, subscription_id, and
subscription_expires_at from their active subscription.

Usage:
  python scripts/reconcile-stripe-subscriptions.py          # dry run (shows what would change)
  python scripts/reconcile-stripe-subscriptions.py --apply  # apply changes
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_env_file = Path(__file__).parent.parent / "apps" / "api" / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

try:
    from azure.cosmos.aio import CosmosClient
except ImportError:
    sys.exit("azure-cosmos not installed.")

try:
    import stripe
except ImportError:
    sys.exit("stripe not installed. Run: pip install stripe")

ACCOUNT   = os.getenv("AZURE_COSMOSDB_ACCOUNT", "").strip()
KEY       = os.getenv("AZURE_COSMOSDB_ACCOUNT_KEY", "").strip()
DATABASE  = os.getenv("AZURE_COSMOSDB_DATABASE", "db_conversation_history").strip()
CONTAINER = os.getenv("AZURE_COSMOSDB_SESSIONS_CONTAINER", "sessions").strip()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
if not stripe.api_key:
    sys.exit("STRIPE_SECRET_KEY not set")

_PLAN_TO_TIER = {
    "ari_elite": "elite", "ari_pro": "elite", "ari_lite": "lite",
    "elite": "elite", "pro": "elite", "lite": "lite",
}

# Feb 19 seeded accounts — skip these, they predate Stripe
_SEEDED_DATE = "2026-02-19"

def _extract_tier_from_sub(sub) -> str:
    """Extract normalized tier from a Stripe subscription object."""
    items = sub.get("items", {}).get("data", [])
    if not items:
        return ""
    price = items[0].get("price", {})
    # Check price metadata first, then plan metadata
    raw = (price.get("metadata") or {}).get("tier", "").strip().lower()
    if not raw:
        raw = (items[0].get("plan", {}).get("metadata") or {}).get("tier", "").strip().lower()
    return _PLAN_TO_TIER.get(raw, raw)


async def main(apply: bool) -> None:
    endpoint = f"https://{ACCOUNT}.documents.azure.com:443/"
    async with CosmosClient(endpoint, credential=KEY) as client:
        container = client.get_database_client(DATABASE).get_container_client(CONTAINER)

        # Find all tiered users missing stripe_customer_id
        unlinked = []
        async for doc in container.query_items("SELECT * FROM c WHERE c.type='user'"):
            tier = (doc.get("tier") or "").strip().lower()
            plan = (doc.get("plan") or "").strip().lower()
            normalized = _PLAN_TO_TIER.get(tier) or _PLAN_TO_TIER.get(plan)
            if not normalized:
                continue
            if doc.get("stripe_customer_id"):
                continue
            created = doc.get("createdAt", "")
            if created.startswith(_SEEDED_DATE):
                continue  # Skip Feb 19 seeded accounts (pre-Stripe)
            unlinked.append(doc)

        print(f"Tiered users missing stripe_customer_id (post-seed): {len(unlinked)}")
        print(f"Mode: {'APPLY' if apply else 'DRY RUN'}\n")

        found = 0
        not_found = 0

        for doc in unlinked:
            email = doc.get("email", "")
            if not email:
                continue

            # Look up Stripe customer by email via REST (avoids SDK version quirks)
            import urllib.request, urllib.parse, json as _json, base64 as _b64
            def _stripe_get(path: str, params: dict = {}) -> dict:
                qs = urllib.parse.urlencode(params)
                url = f"https://api.stripe.com/v1/{path}{'?' + qs if qs else ''}"
                req = urllib.request.Request(url)
                creds = _b64.b64encode(f"{stripe.api_key}:".encode()).decode()
                req.add_header("Authorization", f"Basic {creds}")
                with urllib.request.urlopen(req, timeout=10) as r:
                    return _json.loads(r.read())

            try:
                result = _stripe_get("customers", {"email": email, "limit": "5"})
                customer_list = result.get("data", [])
            except Exception as e:
                print(f"  STRIPE ERROR for {email}: {e}")
                not_found += 1
                continue

            if not customer_list:
                print(f"  NOT IN STRIPE: {email}")
                not_found += 1
                continue

            # Find the customer with an active subscription
            matched_customer = None
            matched_sub = None
            for customer in customer_list:
                try:
                    subs = _stripe_get("subscriptions", {"customer": customer["id"], "status": "active", "limit": "5"})
                    for sub in subs.get("data", []):
                        matched_customer = customer
                        matched_sub = sub
                        break
                except Exception:
                    pass
                if matched_sub:
                    break

            if not matched_customer or not matched_sub:
                # Try any subscription (e.g. canceled)
                for customer in customer_list:
                    try:
                        subs = _stripe_get("subscriptions", {"customer": customer["id"], "limit": "5"})
                        for sub in subs.get("data", []):
                            matched_customer = customer
                            matched_sub = sub
                            break
                    except Exception:
                        pass
                    if matched_sub:
                        break

            if not matched_customer:
                print(f"  NO SUBSCRIPTION IN STRIPE: {email}")
                not_found += 1
                continue

            cus_id  = matched_customer["id"]
            sub_id  = matched_sub["id"] if matched_sub else None
            status  = matched_sub.get("status") if matched_sub else None
            expires = None
            stripe_tier = ""
            if matched_sub:
                period_end = matched_sub.get("items", {}).get("data", [{}])[0].get("current_period_end")
                if period_end:
                    expires = datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat()
                stripe_tier = _extract_tier_from_sub(matched_sub)

            print(f"  FOUND: {email:<45}  cus={cus_id}  sub={sub_id}  tier={stripe_tier}  status={status}  expires={expires[:10] if expires else 'N/A'}")
            found += 1

            if apply:
                doc["stripe_customer_id"] = cus_id
                if sub_id:
                    doc["subscription_id"] = sub_id
                if status:
                    doc["subscription_status"] = status
                if expires:
                    doc["subscription_expires_at"] = expires
                if stripe_tier and stripe_tier != doc.get("tier"):
                    print(f"    ⚠ tier mismatch: cosmos={doc.get('tier')} stripe={stripe_tier} — keeping cosmos value")
                doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                await container.upsert_item(doc)

        print(f"\nSummary: {found} found in Stripe, {not_found} not found")
        if not apply:
            print("\nRun with --apply to write changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to Cosmos (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
