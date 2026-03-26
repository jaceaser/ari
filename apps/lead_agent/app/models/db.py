"""
SQLAlchemy 2.x ORM models — map directly to Azure SQL tables.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Geography(Base):
    __tablename__ = "geographies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geo_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    county_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fips_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    zillow_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority_tier: Mapped[int] = mapped_column(SmallInteger, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("geo_type", "name", "state_code", name="uq_geography"),
    )


class LeadType(Base):
    __tablename__ = "lead_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    url_template: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_interval_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_state: Mapped[str] = mapped_column(String(2), nullable=False)
    address_zip: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    geography_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("geographies.id"), nullable=True
    )
    beds: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    baths: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lot_area_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    lot_area_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    zillow_zpid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parcel_apn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    observations: Mapped[list[PropertyObservation]] = relationship(back_populates="property")

    __table_args__ = (
        Index("ix_properties_zip", "address_zip"),
        Index("ix_properties_state_city", "address_state", "address_city"),
        Index("ix_properties_zpid", "zillow_zpid"),
        Index("ix_properties_geography", "geography_id"),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    geography_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("geographies.id"), nullable=False
    )
    lead_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_types.id"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_month: Mapped[str] = mapped_column(String(7), nullable=False)
    zillow_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_blob_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observations: Mapped[list[PropertyObservation]] = relationship(back_populates="scrape_run")

    __table_args__ = (
        Index("ix_scrape_runs_geo_lt", "geography_id", "lead_type_id"),
        Index("ix_scrape_runs_month", "run_month"),
        Index("ix_scrape_runs_status", "status"),
    )


class PropertyObservation(Base):
    __tablename__ = "property_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.id"), nullable=False
    )
    scrape_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scrape_runs.id"), nullable=False
    )
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    price_per_sqft: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    listing_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_on_market: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zillow_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run_month: Mapped[str] = mapped_column(String(7), nullable=False)

    property: Mapped[Property] = relationship(back_populates="observations")
    scrape_run: Mapped[ScrapeRun] = relationship(back_populates="observations")

    __table_args__ = (
        UniqueConstraint("property_id", "scrape_run_id", name="uq_observation"),
        Index("ix_observations_property", "property_id"),
        Index("ix_observations_run", "scrape_run_id"),
        Index("ix_observations_month", "run_month"),
    )


class LeadListDefinition(Base):
    __tablename__ = "lead_list_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geography_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("geographies.id"), nullable=False
    )
    lead_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_types.id"), nullable=False
    )
    list_month: Mapped[str] = mapped_column(String(7), nullable=False)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("scrape_runs.id"), nullable=True
    )
    property_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "geography_id", "lead_type_id", "list_month", name="uq_lead_list"
        ),
        Index("ix_lead_lists_geo_lt", "geography_id", "lead_type_id"),
        Index("ix_lead_lists_month", "list_month"),
    )


class LeadListMembership(Base):
    __tablename__ = "lead_list_membership"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_list_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_list_definitions.id"), nullable=False
    )
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.id"), nullable=False
    )
    observation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("property_observations.id"), nullable=True
    )
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("lead_list_id", "property_id", name="uq_list_membership"),
        Index("ix_membership_list", "lead_list_id"),
        Index("ix_membership_property", "property_id"),
    )


class PropertyTag(Base):
    __tablename__ = "property_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tag_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class PropertyTagMap(Base):
    __tablename__ = "property_tag_map"

    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.id"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("property_tags.id"), primary_key=True
    )
    tagged_by: Mapped[str] = mapped_column(String(50), default="system")
    tagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_tag_map_tag", "tag_id"),)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)


class UserPropertyMap(Base):
    __tablename__ = "user_property_map"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.id"), nullable=False
    )
    pipeline_stage_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pipeline_stages.id"), nullable=True
    )
    saved_from_list_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("lead_list_definitions.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_trace_status: Mapped[str] = mapped_column(String(20), default="none")
    comp_status: Mapped[str] = mapped_column(String(20), default="none")
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_user_property"),
        Index("ix_upm_user", "user_id"),
        Index("ix_upm_property", "property_id"),
        Index("ix_upm_stage", "pipeline_stage_id"),
    )


class UserLeadRequest(Base):
    __tablename__ = "user_lead_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    geography_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("geographies.id"), nullable=False
    )
    lead_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_types.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    served_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    lead_list_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("lead_list_definitions.id"), nullable=True
    )
    properties_served: Mapped[int] = mapped_column(Integer, default=0)
