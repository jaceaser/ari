"""
ScrapingBee HTTP client for Zillow page fetching.
Handles proxy routing, raw artifact storage, and retry logic.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


class ScrapingBeeClient:
    def __init__(self, api_key: str, timeout: int = 90):
        self.api_key = api_key
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=60),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def fetch(self, url: str) -> Optional[bytes]:
        """Fetch URL through ScrapingBee. Returns raw bytes or None on non-200."""
        try:
            resp = requests.get(
                SCRAPINGBEE_URL,
                params={
                    "api_key": self.api_key,
                    "url": url,
                    "premium_proxy": "true",
                    "country_code": "us",
                    "render_js": "true",
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.content
            logger.warning("ScrapingBee %d for %s", resp.status_code, url[:80])
            return None
        except requests.RequestException as exc:
            logger.warning("ScrapingBee fetch error (will retry): %s", exc)
            raise


class ScrapeService:
    def __init__(self):
        s = get_settings()
        self._client = ScrapingBeeClient(s.scrapingbee_api_key, s.scrape_timeout_seconds)
        self._blob_conn = s.azure_storage_connection_string
        self._raw_container = s.raw_artifacts_container

    def fetch_page(self, url: str) -> Optional[bytes]:
        return self._client.fetch(url)

    def store_raw_artifact(self, run_uuid: str, page: int, content: bytes) -> Optional[str]:
        """Store raw HTML to Azure Blob. Returns blob path or None if storage not configured."""
        if not self._blob_conn or not content:
            return None
        try:
            from azure.storage.blob import BlobServiceClient
            blob_name = f"raw/{run_uuid}/page_{page:03d}.html"
            client = BlobServiceClient.from_connection_string(self._blob_conn)
            container = client.get_container_client(self._raw_container)
            container.upload_blob(blob_name, content, overwrite=True)
            return blob_name
        except Exception as exc:
            logger.warning("Raw artifact storage failed: %s", exc)
            return None
