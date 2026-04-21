"""
Central configuration via pydantic-settings.
All secrets come from environment variables or Azure Key Vault at startup.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Azure Database for PostgreSQL Flexible Server
    azure_pg_host: str = Field(..., alias="AZURE_PG_HOST")
    azure_pg_database: str = Field("ari_leads", alias="AZURE_PG_DATABASE")
    azure_pg_username: str = Field(..., alias="AZURE_PG_USERNAME")
    azure_pg_password: str = Field(..., alias="AZURE_PG_PASSWORD")
    azure_pg_port: int = Field(5432, alias="AZURE_PG_PORT")

    # ScrapingBee
    scrapingbee_api_key: str = Field(..., alias="SCRAPINGBEE_API_KEY")
    scrape_max_pages: int = Field(5, alias="SCRAPE_MAX_PAGES")
    scrape_timeout_seconds: int = Field(90, alias="SCRAPE_TIMEOUT_SECONDS")

    # Azure Blob (for raw HTML artifacts)
    azure_storage_connection_string: Optional[str] = Field(
        None, alias="AZURE_STORAGE_CONNECTION_STRING"
    )
    raw_artifacts_container: str = Field("lead-agent-raw", alias="RAW_ARTIFACTS_CONTAINER")

    # Azure Service Bus (for async on-demand jobs)
    service_bus_connection_string: Optional[str] = Field(
        None, alias="SERVICE_BUS_CONNECTION_STRING"
    )
    service_bus_queue_name: str = Field("lead-agent-ondemand", alias="SERVICE_BUS_QUEUE_NAME")

    # Agent behavior
    run_month_override: Optional[str] = Field(None, alias="RUN_MONTH_OVERRIDE")
    cache_ttl_days_tier1: int = Field(1, alias="CACHE_TTL_DAYS_TIER1")
    cache_ttl_days_tier2: int = Field(7, alias="CACHE_TTL_DAYS_TIER2")
    cache_ttl_days_tier3: int = Field(14, alias="CACHE_TTL_DAYS_TIER3")
    max_concurrent_scrapes: int = Field(5, alias="MAX_CONCURRENT_SCRAPES")

    # Obituary scraper — backfill vs daily sync have different default concurrency
    # because the initial 365-day backfill has ~234k records across many pages.
    obituary_backfill_concurrency: int = Field(25, alias="OBITUARY_BACKFILL_CONCURRENCY")
    obituary_concurrency: int = Field(5, alias="OBITUARY_CONCURRENCY")
    obituary_request_delay_ms_min: int = Field(500, alias="OBITUARY_REQUEST_DELAY_MS_MIN")
    obituary_request_delay_ms_max: int = Field(2000, alias="OBITUARY_REQUEST_DELAY_MS_MAX")

    # Observability
    app_insights_connection_string: Optional[str] = Field(
        None, alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    @property
    def sql_connection_string(self) -> str:
        return (
            f"postgresql+psycopg2://{self.azure_pg_username}:{self.azure_pg_password}"
            f"@{self.azure_pg_host}:{self.azure_pg_port}/{self.azure_pg_database}"
            "?sslmode=require"
        )

    def run_month(self) -> str:
        if self.run_month_override:
            return self.run_month_override
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m")


@lru_cache
def get_settings() -> Settings:
    return Settings()
