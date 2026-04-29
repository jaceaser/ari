"""Geography and lead type repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.db import Geography, LeadType
from app.models.domain import GeoType, GeographyRecord, LeadTypeRecord, LeadTypeSlug


class GeographyRepo:
    def __init__(self, db: Session):
        self._db = db

    def get_by_slug(self, zillow_slug: str) -> Optional[GeographyRecord]:
        row = self._db.query(Geography).filter(Geography.zillow_slug == zillow_slug).first()
        return self._to_domain(row) if row else None

    def get_active_by_tier(self, max_tier: int = 1, min_tier: int = 1) -> list[GeographyRecord]:
        rows = (
            self._db.query(Geography)
            .filter(
                Geography.is_active == True,
                Geography.priority_tier >= min_tier,
                Geography.priority_tier <= max_tier,
            )
            .order_by(Geography.priority_tier, Geography.state_code, Geography.name)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def get_all_active(self) -> list[GeographyRecord]:
        rows = (
            self._db.query(Geography)
            .filter(Geography.is_active == True)
            .order_by(Geography.priority_tier, Geography.state_code)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def upsert_from_seed(self, data: dict) -> Geography:
        existing = (
            self._db.query(Geography)
            .filter(
                Geography.geo_type == data["geo_type"],
                Geography.name == data["name"],
                Geography.state_code == data["state_code"],
            )
            .first()
        )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        row = Geography(**data)
        self._db.add(row)
        self._db.flush()
        return row

    def get_active_lead_types(self) -> list[LeadTypeRecord]:
        rows = self._db.query(LeadType).filter(LeadType.is_active == True).all()
        return [
            LeadTypeRecord(
                id=r.id,
                slug=LeadTypeSlug(r.slug),
                display_name=r.display_name,
                url_template=r.url_template,
                refresh_interval_days=r.refresh_interval_days,
            )
            for r in rows
        ]

    @staticmethod
    def _to_domain(row: Geography) -> GeographyRecord:
        return GeographyRecord(
            id=row.id,
            geo_type=GeoType(row.geo_type),
            name=row.name,
            state_code=row.state_code,
            county_name=row.county_name,
            fips_code=row.fips_code,
            zillow_slug=row.zillow_slug,
            priority_tier=row.priority_tier,
        )
