"""
Lead generation service ported from legacy/lead_gen.py.

Provides:
- Zillow property scraping via ScrapingBee
- Attorney directory scraping
- Bricked API comp retrieval
- Caching via Cosmos + Excel upload to Azure Blob

All external clients are lazily initialized.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from services.azure_blob import AzureBlobService
from services.cosmos_db import CosmosLeadGenClient

logger = logging.getLogger(__name__)

# Lazy imports
_requests = None
_BeautifulSoup = None
_httpx = None


def _ensure_requests():
    global _requests
    if _requests is None:
        import requests
        _requests = requests
    return _requests


def _ensure_bs4():
    global _BeautifulSoup
    if _BeautifulSoup is None:
        from bs4 import BeautifulSoup
        _BeautifulSoup = BeautifulSoup
    return _BeautifulSoup


def _ensure_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


# Column config matching legacy
COLUMNS_TO_KEEP = [
    "addressStreet", "addressCity", "addressState", "addressZipcode",
    "beds", "baths", "lotAreaValue", "lotAreaUnit",
    "price", "address", "detailUrl",
]

COLUMN_MAPPING = {
    "address": "Full Address",
    "addressCity": "City",
    "price": "Asking Price",
    "detailUrl": "Property URL",
    "addressStreet": "Address",
    "addressState": "State",
    "addressZipcode": "Zip",
    "beds": "Beds",
    "baths": "Bathrooms",
    "lotAreaValue": "Lot Size",
    "lotAreaUnit": "Lot Unit",
}


def _get_scrapingbee_key() -> Optional[str]:
    return (os.getenv("SCRAPINGBEE_API_KEY") or os.getenv("SCRAPING_BEE_API_KEY") or "").strip() or None


async def fetch_page_content(url: str) -> Optional[bytes]:
    """Fetch a page via ScrapingBee proxy."""
    api_key = _get_scrapingbee_key()
    if not api_key:
        logger.warning("SCRAPINGBEE_API_KEY not set; cannot scrape.")
        return None

    requests = _ensure_requests()
    try:
        response = requests.get(
            url="https://app.scrapingbee.com/api/v1/",
            params={
                "api_key": api_key,
                "url": url,
                "premium_proxy": "true",
                "country_code": "us",
                "render_js": "false",
            },
            timeout=60,
        )
        return response.content
    except Exception as exc:
        logger.error("ScrapingBee fetch failed: %s", exc)
        return None


def parse_property_data(html_content: bytes) -> pd.DataFrame:
    """Parse Zillow property listings from HTML."""
    empty = pd.DataFrame(columns=[COLUMN_MAPPING[c] for c in COLUMNS_TO_KEEP])
    if not html_content:
        return empty

    BeautifulSoup = _ensure_bs4()
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        search_pattern = re.compile(r'"searchResults":(\{.*?\}\}\})', re.DOTALL)

        for script in soup.find_all("script"):
            content = script.string
            if not content:
                continue
            match = search_pattern.search(content)
            if not match:
                continue

            data = match.group(1)
            parsed = json.loads(f'{{"searchResults": {data[:-1]}}}')
            listings = parsed["searchResults"]["listResults"]
            if not listings:
                continue

            for listing in listings:
                home_info = listing.get("hdpData", {}).get("homeInfo", {})
                listing["lotAreaValue"] = home_info.get("lotAreaValue")
                listing["lotAreaUnit"] = home_info.get("lotAreaUnit")

            df = pd.DataFrame(listings)
            final = pd.DataFrame(columns=[COLUMN_MAPPING[c] for c in COLUMNS_TO_KEEP])
            available = [c for c in COLUMNS_TO_KEEP if c in df.columns]
            for col in available:
                final[COLUMN_MAPPING[col]] = df[col]
            return final

        return empty
    except Exception as exc:
        logger.error("Error parsing property data: %s", exc)
        return empty


async def fetch_page_data(input_url: str, page: int) -> pd.DataFrame:
    """Fetch a single page of Zillow results."""
    if page == 1:
        paginated_url = input_url
    else:
        base_url, query_string = input_url.split("?", 1)
        paginated_url = f"{base_url}{page}_p/?{query_string}"

    paginated_url = paginated_url.replace(
        '"pagination":{}',
        f'"pagination":{{"currentPage":{page}}}',
    )
    content = await fetch_page_content(paginated_url)
    return parse_property_data(content)


def _extract_total_results(html_content: bytes) -> int:
    """Extract total result count from Zillow HTML using multiple strategies."""
    if not html_content:
        return 0

    BeautifulSoup = _ensure_bs4()
    total = 0

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Strategy 1: result-count span (legacy Zillow)
        tag = soup.find("span", class_="result-count")
        if tag:
            text = tag.text.replace(",", "").strip()
            match = re.search(r"(\d+)", text)
            if match:
                total = int(match.group(1))
                logger.info("Result count from span: %d", total)
                return total

        # Strategy 2: Extract totalResultCount from JSON in script tags
        for script in soup.find_all("script"):
            content = script.string
            if not content:
                continue
            # Look for totalResultCount in the searchResults JSON
            count_match = re.search(r'"totalResultCount"\s*:\s*(\d+)', content)
            if count_match:
                total = int(count_match.group(1))
                logger.info("Result count from JSON totalResultCount: %d", total)
                return total
            # Also try totalPages
            pages_match = re.search(r'"totalPages"\s*:\s*(\d+)', content)
            if pages_match:
                total = int(pages_match.group(1)) * 41  # ~41 results per page
                logger.info("Result count estimated from totalPages: %d", total)
                return total

        # Strategy 3: count listResults directly in JSON
        search_pattern = re.compile(r'"listResults"\s*:\s*\[', re.DOTALL)
        for script in soup.find_all("script"):
            content = script.string
            if not content or not search_pattern.search(content):
                continue
            results_match = re.search(r'"searchResults":\s*\{[^}]*"listResults"\s*:\s*\[(.*?)\]\s*\}', content, re.DOTALL)
            if results_match:
                # If we got 40+ results on page 1, there are likely more pages
                comma_count = results_match.group(1).count('"zpid"')
                if comma_count >= 40:
                    total = comma_count * 3  # Estimate ~3 pages
                    logger.info("Result count estimated from listing count (%d on page 1): %d", comma_count, total)
                    return total

    except Exception as exc:
        logger.error("Error extracting result count: %s", exc)

    return total


async def get_all_pages(input_url: str, max_pages: int = 5) -> pd.DataFrame:
    """Fetch up to max_pages of Zillow property results."""
    import asyncio

    first_content = await fetch_page_content(input_url)
    first_df = parse_property_data(first_content)

    # Determine total pages needed
    total_results = _extract_total_results(first_content)
    first_page_count = len(first_df)

    # If page 1 returned 40+ results but we couldn't determine total,
    # assume there are more pages and try at least 3
    if total_results == 0 and first_page_count >= 40:
        needed = min(3, max_pages)
        logger.info("No total count found but page 1 had %d results; fetching %d pages", first_page_count, needed)
    elif total_results > 0:
        needed = min(math.ceil(total_results / 41), max_pages)
    else:
        needed = 1

    if needed <= 1:
        return first_df

    logger.info("Fetching pages 2-%d (total_results=%d, max_pages=%d)", needed, total_results, max_pages)
    tasks = [fetch_page_data(input_url, p) for p in range(2, needed + 1)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    frames = [first_df]
    for r in results:
        if isinstance(r, pd.DataFrame) and not r.empty:
            frames.append(r)

    combined = pd.concat(frames, ignore_index=True) if frames else first_df
    logger.info("Total properties across %d pages: %d", len(frames), len(combined))
    return combined


def parse_attorneys(content: bytes) -> pd.DataFrame:
    """Parse attorney JSON-LD from directory page HTML."""
    BeautifulSoup = _ensure_bs4()
    soup = BeautifulSoup(content, "html.parser")
    scripts = soup.find_all("script", {"type": "application/ld+json"})

    for script in scripts:
        try:
            data = json.loads(script.string)
            if "@graph" not in data:
                continue

            rows = []
            for entry in data["@graph"]:
                rows.append({
                    "name": entry.get("name", "").strip(),
                    "telephone": entry.get("telephone", ""),
                    "website": entry.get("url", ""),
                    "street_address": entry.get("address", {}).get("streetAddress", ""),
                    "city": entry.get("address", {}).get("addressLocality", ""),
                    "state": entry.get("address", {}).get("addressRegion", ""),
                    "zip": entry.get("address", {}).get("postalCode", ""),
                })
            return pd.DataFrame(rows)
        except (json.JSONDecodeError, KeyError):
            continue

    return pd.DataFrame()


async def get_all_attorneys(input_url: str) -> pd.DataFrame:
    """Scrape attorney directory via ScrapingBee."""
    content = await fetch_page_content(input_url)
    if not content:
        return pd.DataFrame()
    return parse_attorneys(content)


async def get_properties(url: str, filename: str, max_pages: int = 5) -> dict[str, Any]:
    """
    Full lead-gen pipeline: check cache, scrape Zillow, upload Excel, cache result.
    Returns a dict with status, preview, excel_link, count.
    """
    cache_client = CosmosLeadGenClient.get_instance()
    blob_service = AzureBlobService.get_instance()

    # Check cache — skip if cached result had no properties
    if cache_client:
        try:
            cached = await cache_client.get_cached_data(url)
            if cached:
                df = pd.DataFrame(json.loads(cached["data"]))
                if not df.empty:
                    logger.info("Using cached lead data for %s (%d results)", url, len(df))
                    preview = AzureBlobService.get_dataframe_preview(df)
                    return {
                        "status": "ok",
                        "source": "cache",
                        "preview": preview,
                        "excel_link": cached.get("excel_link", ""),
                        "properties_count": len(df),
                    }
                else:
                    logger.info("Cached data for %s had 0 results; re-scraping", url)
        except Exception as exc:
            logger.error("Cache lookup failed: %s", exc)

    # Scrape
    df = await get_all_pages(url, max_pages=max_pages)
    if df.empty:
        return {"status": "no_results", "message": "No leads were found.", "properties_count": 0}

    preview = AzureBlobService.get_dataframe_preview(df)
    excel_link = ""

    # Upload to blob
    upload_error = ""
    if blob_service:
        try:
            excel_link = blob_service.upload_dataframe(
                container_name="leads", file_name=filename, df=df
            )
        except Exception as exc:
            logger.error("Excel upload failed: %s", exc)
            upload_error = f"Excel file upload failed: {exc}"

    # Cache only if upload succeeded
    if cache_client and excel_link:
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            await cache_client.write_to_cache(url, {
                "data": json.dumps(df.to_dict(orient="records")),
                "excel_link": excel_link,
            }, timestamp)
        except Exception as exc:
            logger.error("Cache write failed: %s", exc)

    result = {
        "status": "ok",
        "source": "scrape",
        "preview": preview,
        "excel_link": excel_link,
        "properties_count": len(df),
    }
    if upload_error:
        result["upload_error"] = upload_error
    return result


async def get_attorneys(url: str, filename: str) -> dict[str, Any]:
    """
    Full attorney pipeline: check cache, scrape, upload Excel, cache result.
    """
    cache_client = CosmosLeadGenClient.get_instance()
    blob_service = AzureBlobService.get_instance()

    # Check cache
    if cache_client:
        try:
            cached = await cache_client.get_cached_data(url)
            if cached:
                df = pd.DataFrame(json.loads(cached["data"]))
                preview = AzureBlobService.get_dataframe_preview(df)
                return {
                    "status": "ok",
                    "source": "cache",
                    "preview": preview,
                    "excel_link": cached.get("excel_link", ""),
                    "attorneys_count": len(df),
                }
        except Exception as exc:
            logger.error("Attorney cache lookup failed: %s", exc)

    # Scrape
    df = await get_all_attorneys(url)
    if df.empty:
        return {"status": "no_results", "message": "No attorneys were found.", "attorneys_count": 0}

    preview = AzureBlobService.get_dataframe_preview(df)
    excel_link = ""

    upload_error = ""
    if blob_service:
        try:
            excel_link = blob_service.upload_dataframe(
                container_name="leads", file_name=filename, df=df, sheet_name="Attorneys"
            )
        except Exception as exc:
            logger.error("Attorney Excel upload failed: %s", exc)
            upload_error = f"Excel file upload failed: {exc}"

    if cache_client and excel_link:
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            await cache_client.write_to_cache(url, {
                "data": json.dumps(df.to_dict(orient="records")),
                "excel_link": excel_link,
            }, timestamp)
        except Exception as exc:
            logger.error("Attorney cache write failed: %s", exc)

    result = {
        "status": "ok",
        "source": "scrape",
        "preview": preview,
        "excel_link": excel_link,
        "attorneys_count": len(df),
    }
    if upload_error:
        result["upload_error"] = upload_error
    return result
