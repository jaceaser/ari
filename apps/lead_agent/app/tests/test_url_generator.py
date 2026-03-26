"""Tests for the deterministic URL generator."""
import pytest
from app.models.domain import LeadTypeSlug
from app.services.url_generator import LEAD_TYPE_TEMPLATES, generate_url


def test_all_lead_types_covered():
    for slug in LeadTypeSlug:
        assert slug in LEAD_TYPE_TEMPLATES, f"No template for {slug}"


def test_placeholder_replaced():
    for slug, meta in LEAD_TYPE_TEMPLATES.items():
        url = generate_url("harris-county-tx", meta["url_template"])
        assert "%%GEO_SLUG%%" not in url, f"Placeholder not replaced for {slug}"
        assert "harris-county-tx" in url
        assert "zillow.com" in url


def test_different_geos_produce_different_urls():
    meta = LEAD_TYPE_TEMPLATES[LeadTypeSlug.FSBO]
    url1 = generate_url("harris-county-tx", meta["url_template"])
    url2 = generate_url("los-angeles-county-ca", meta["url_template"])
    assert url1 != url2


def test_all_templates_are_https():
    for slug, meta in LEAD_TYPE_TEMPLATES.items():
        url = generate_url("test-tx", meta["url_template"])
        assert url.startswith("https://"), f"{slug} URL is not HTTPS"
