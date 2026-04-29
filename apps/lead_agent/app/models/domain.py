"""
Pydantic domain models — in-memory representations during pipeline execution.
These are NOT ORM models. They represent data flowing through the pipeline.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class GeoType(StrEnum):
    COUNTY = "county"
    CITY = "city"
    ZIP = "zip"
    METRO = "metro"


class LeadTypeSlug(StrEnum):
    FSBO = "fsbo"
    AS_IS = "as_is"
    PRE_FORECLOSURE = "pre_foreclosure"
    LAND = "land"
    TIRED_LANDLORD = "tired_landlord"
    FIXER_UPPER = "fixer_upper"
    SUBJECT_TO = "subject_to"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class TriggerType(StrEnum):
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"


class GeographyRecord(BaseModel):
    id: int
    geo_type: GeoType
    name: str
    state_code: str
    county_name: Optional[str]
    fips_code: Optional[str]
    zillow_slug: str
    priority_tier: int  # 1=top100, 2=standard, 3=long-tail


class LeadTypeRecord(BaseModel):
    id: int
    slug: LeadTypeSlug
    display_name: str
    url_template: str
    refresh_interval_days: int = 30


class PropertyRaw(BaseModel):
    """Raw parsed output from Zillow HTML — before normalization and dedup."""
    source_listing_id: Optional[str] = None  # Zillow zpid
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    full_address: Optional[str] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_area_value: Optional[float] = None
    lot_area_unit: Optional[str] = None
    price: Optional[float] = None
    listing_status: Optional[str] = None
    days_on_market: Optional[int] = None
    detail_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raw_json: Optional[str] = None


class NormalizedProperty(BaseModel):
    """Post-normalization — ready for dedup and persistence."""
    address_line1: str
    address_city: str
    address_state: str
    address_zip: Optional[str]
    canonical_hash: str  # SHA-256

    zillow_zpid: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_area_value: Optional[float] = None
    lot_area_unit: Optional[str] = None
    price: Optional[float] = None
    listing_status: Optional[str] = None
    days_on_market: Optional[int] = None
    detail_url: Optional[str] = None
    raw_json: Optional[str] = None


class ScrapeRunContext(BaseModel):
    run_uuid: str
    run_id: int
    geography: GeographyRecord
    lead_type: LeadTypeRecord
    trigger_type: TriggerType
    triggered_by: Optional[str]
    run_month: str
    zillow_url: str
    started_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class RunResult(BaseModel):
    run_uuid: str
    status: RunStatus
    geography_slug: str
    lead_type_slug: str
    run_month: str
    pages_fetched: int
    raw_count: int
    new_count: int
    updated_count: int
    duplicate_count: int
    expired_count: int = 0
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
