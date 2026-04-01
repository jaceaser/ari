"""
Dignity Memorial obituary search API client.

Calls the internal JSON search API directly via ScrapingBee (needed to bypass
Cloudflare).  No AI extraction — the API returns structured JSON.

Discovered endpoint:
  https://cdn-obituaries.dignitymemorial.com/api/v1/obituaries/search
  ?brand=DM&lang=en-us&creationDate=<N>&pageNo=<P>&size=50

Parameters:
  creationDate  – look-back window in days (365 for backfill, 1-3 for daily sync)
  pageNo        – 1-based page number
  size          – results per page (max observed: 50)
  locationState – optional 2-letter state filter (e.g. "TX")
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1"
_OBITUARIES_API = "https://cdn-obituaries.dignitymemorial.com/api/v1/obituaries/search"
SOURCE_SITE = "dignity_memorial"


class ObituaryScraper:
    def __init__(self, api_key: str, timeout: int = 60):
        self._api_key = api_key
        self._timeout = timeout

    def build_api_url(self, creation_date: int, page_no: int, state: Optional[str] = None) -> str:
        params: dict[str, Any] = {
            "brand": "DM",
            "lang": "en-us",
            "creationDate": creation_date,
            "pageNo": page_no,
            "size": 50,
        }
        if state:
            params["locationState"] = state
        return f"{_OBITUARIES_API}?{urllib.parse.urlencode(params)}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_page(
        self, date_filter: int, page_no: int, state: Optional[str] = None
    ) -> tuple[Optional[list[dict]], str]:
        """
        Fetch one page of obituaries from the Dignity Memorial search API.

        Returns (results_list, source_url).
        results_list is None on non-200 non-retryable responses.
        Raises requests.RequestException on 429/5xx for tenacity to retry.
        """
        api_url = self.build_api_url(date_filter, page_no, state)

        try:
            resp = requests.get(
                SCRAPINGBEE_URL,
                params={
                    "api_key": self._api_key,
                    "url": api_url,
                    "render_js": "false",
                    "premium_proxy": "true",
                    "country_code": "us",
                },
                timeout=self._timeout,
            )
        except requests.Timeout:
            logger.warning("scrapingbee_timeout page=%d url=%s", page_no, api_url)
            raise
        except requests.RequestException as exc:
            logger.warning("scrapingbee_request_error page=%d err=%s", page_no, exc)
            raise

        if resp.status_code == 200:
            try:
                data = resp.json()
                return data.get("results") or [], api_url
            except Exception as exc:
                logger.warning("json_parse_error page=%d err=%s body=%r", page_no, exc, resp.text[:200])
                return [], api_url

        if resp.status_code == 429:
            logger.warning("scrapingbee_rate_limited page=%d — will retry", page_no)
            raise requests.RequestException(f"rate_limited status=429 page={page_no}")

        if resp.status_code >= 500:
            logger.warning("scrapingbee_server_error status=%d page=%d", resp.status_code, page_no)
            raise requests.RequestException(f"server_error status={resp.status_code} page={page_no}")

        logger.warning("scrapingbee_unexpected status=%d page=%d", resp.status_code, page_no)
        return None, api_url
