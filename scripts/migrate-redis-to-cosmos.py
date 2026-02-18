"""
One-time migration script: Redis → Cosmos DB

Reads all subscription:* keys from the legacy Redis instance and creates
corresponding user documents in Cosmos DB with subscription data.

Usage:
    # Set env vars (or use .env in apps/api/)
    export REDIS_HOST=ari-production.redis.cache.windows.net
    export REDIS_PORT=6380
    export REDIS_PASSWORD=...
    export AZURE_COSMOSDB_ACCOUNT=...
    export AZURE_COSMOSDB_ACCOUNT_KEY=...

    python scripts/migrate-redis-to-cosmos.py [--dry-run]
"""

import asyncio
import json
import logging
import os
import ssl
import sys
import uuid

# Allow importing from apps/api
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate")


def _load_env():
    """Load .env from apps/api if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", "apps", "api", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info("Loaded env from %s", env_path)
    except ImportError:
        pass


async def get_redis_client():
    """Create async Redis client matching legacy connection settings."""
    import redis.asyncio as aioredis

    host = os.environ.get("REDIS_HOST", "").strip()
    port = int(os.environ.get("REDIS_PORT", "6380"))
    password = os.environ.get("REDIS_PASSWORD", "").strip()

    if not host or not password:
        logger.error("REDIS_HOST and REDIS_PASSWORD must be set")
        sys.exit(1)

    client = aioredis.Redis(
        host=host,
        port=port,
        password=password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        ssl_check_hostname=False,
        decode_responses=True,
        socket_timeout=30,
        socket_connect_timeout=30,
        retry_on_timeout=True,
        db=0,
    )

    # Test connection
    await client.ping()
    logger.info("Connected to Redis at %s:%s", host, port)
    return client


def derive_user_id(email: str) -> str:
    """Deterministic user ID from email — matches magic link verify logic."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{email}"))


def map_status(redis_status: str) -> str:
    """Map legacy Redis subscription status to Cosmos format."""
    active_statuses = {"active", "pending", "trialing"}
    if redis_status in active_statuses:
        return "active"
    return redis_status  # cancelled, expired, trash, etc.


async def migrate(dry_run: bool = False):
    _load_env()

    redis_client = await get_redis_client()

    # Import Cosmos client from the API
    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        logger.error("Cosmos DB not configured — check AZURE_COSMOSDB_* env vars")
        sys.exit(1)

    # Scan all subscription:* keys
    logger.info("Scanning Redis for subscription:* keys...")
    cursor = 0
    migrated = 0
    skipped = 0
    errors = 0

    while True:
        cursor, keys = await redis_client.scan(cursor, match="subscription:*", count=100)

        for key in keys:
            # Skip subscription_id:* keys (indexed by sub ID, not email)
            if key.startswith("subscription_id:"):
                continue

            email = key.replace("subscription:", "", 1)
            try:
                raw = await redis_client.get(key)
                if not raw:
                    skipped += 1
                    continue

                data = json.loads(raw)
                user_email = data.get("user_email", email)
                user_id = derive_user_id(user_email)

                stripe_data = {
                    "subscription_status": map_status(data.get("status", "")),
                    "subscription_id": data.get("subscription_id"),
                    "plan": data.get("plan_type"),
                    "subscription_expires_at": data.get("next_payment"),
                    "legacy_redis_migrated": True,
                }

                if dry_run:
                    logger.info(
                        "[DRY RUN] Would migrate %s → user_id=%s plan=%s status=%s",
                        user_email, user_id, stripe_data["plan"], stripe_data["subscription_status"],
                    )
                else:
                    # Ensure user exists, then update subscription
                    await cosmos.ensure_user(user_id, user_email)
                    await cosmos.update_user_subscription(user_id, stripe_data)
                    logger.info(
                        "Migrated %s → user_id=%s plan=%s status=%s",
                        user_email, user_id, stripe_data["plan"], stripe_data["subscription_status"],
                    )

                migrated += 1

            except Exception:
                logger.exception("Failed to migrate key %s", key)
                errors += 1

        if cursor == 0:
            break

    # Also log active_subscriptions set membership for cross-reference
    try:
        active_emails = await redis_client.smembers("active_subscriptions")
        logger.info("Active subscriptions set contains %d emails", len(active_emails))
    except Exception:
        pass

    await redis_client.aclose()

    action = "Would migrate" if dry_run else "Migrated"
    logger.info(
        "Done. %s: %d, Skipped: %d, Errors: %d",
        action, migrated, skipped, errors,
    )


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        logger.info("Running in DRY RUN mode — no writes to Cosmos")
    asyncio.run(migrate(dry_run=dry_run))
