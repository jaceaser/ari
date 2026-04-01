"""
ScrapingBee client for Dignity Memorial obituary listing pages.
Uses AI extraction to get structured JSON output (name, city, state).
"""
from __future__ import annotations

import logging
from typing import Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1"
DIGNITY_MEMORIAL_BASE = "https://www.dignitymemorial.com/obituaries"
SOURCE_SITE = "dignity_memorial"

_AI_QUERY = (
    "Give me all the people who passed away, their city, state, date of birth, "
    "date they passed away, and link to their obituary. "
    "in JSON format with the fields being name, city, state, date_of_death, "
    "date_of_birth, and obituary_link"
)


class ObituaryScraper:
    def __init__(self, api_key: str, timeout: int = 90):
        self._api_key = api_key
        self._timeout = timeout

    def build_url(self, date_filter: int, page_no: int) -> str:
        return f"{DIGNITY_MEMORIAL_BASE}?creationDateFilter={date_filter}&pageNo={page_no}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_page(self, date_filter: int, page_no: int) -> tuple[Optional[str], str]:
        """
        Fetch one obituary listing page via ScrapingBee AI extraction.

        Returns (response_text, source_url).
        response_text is a JSON string (or None on non-200 non-retryable responses).
        Raises requests.RequestException on 429 / 5xx so tenacity can retry.
        """
        source_url = self.build_url(date_filter, page_no)

        try:
            resp = requests.get(
                SCRAPINGBEE_URL,
                params={
                    "api_key": self._api_key,
                    "url": source_url,
                    "render_js": "false",
                    "ai_query": _AI_QUERY,
                },
                timeout=self._timeout,
            )
        except requests.Timeout:
            logger.warning("scrapingbee_timeout page=%d url=%s", page_no, source_url)
            raise
        except requests.RequestException as exc:
            logger.warning("scrapingbee_request_error page=%d err=%s", page_no, exc)
            raise

        if resp.status_code == 200:
            return resp.text, source_url

        if resp.status_code == 429:
            logger.warning(
                "scrapingbee_rate_limited page=%d — suspected block, will retry",
                page_no,
            )
            raise requests.RequestException(f"rate_limited status=429 page={page_no}")

        if resp.status_code >= 500:
            logger.warning(
                "scrapingbee_server_error status=%d page=%d", resp.status_code, page_no
            )
            raise requests.RequestException(
                f"server_error status={resp.status_code} page={page_no}"
            )

        # 4xx (other than 429) — non-retryable, treat as empty page
        logger.warning(
            "scrapingbee_unexpected status=%d page=%d — treating as empty",
            resp.status_code,
            page_no,
        )
        return None, source_url
