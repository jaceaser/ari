"""
Clear cached lead generation results from Cosmos DB.

This deletes cached scrape data so leads will be re-fetched and new
Excel files with fresh SAS download links will be generated.

Usage:
    python scripts/clear-lead-cache.py           # clear ALL cached leads
    python scripts/clear-lead-cache.py <url>     # clear cache for a specific URL
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "mcp"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clear-cache")


async def main():
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", "apps", "mcp", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass

    from services.cosmos_db import CosmosLeadGenClient

    client = CosmosLeadGenClient.get_instance()
    if not client:
        logger.error("Cosmos LeadGen client not configured — check env vars")
        sys.exit(1)

    url = sys.argv[1] if len(sys.argv) > 1 else None

    if url:
        logger.info("Clearing cache for URL: %s", url)
    else:
        logger.info("Clearing ALL lead cache entries...")

    deleted = await client.clear_cache(url=url)
    logger.info("Deleted %d cached entries.", deleted)


if __name__ == "__main__":
    asyncio.run(main())
