"""Tests for address normalization and canonical hash."""
import pytest
from app.services.normalizer import (
    compute_canonical_hash,
    normalize_address_line1,
    normalize_zip,
)


def test_abbreviation_expansion():
    assert "street" in normalize_address_line1("123 Main St")
    assert "avenue" in normalize_address_line1("456 Oak Ave")
    assert "boulevard" in normalize_address_line1("789 Sunset Blvd")


def test_same_address_different_format_same_hash():
    h1 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    h2 = compute_canonical_hash("123 Main Street", "Houston", "TX", "77001")
    assert h1 == h2


def test_different_addresses_different_hash():
    h1 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    h2 = compute_canonical_hash("456 Oak Ave", "Houston", "TX", "77001")
    assert h1 != h2


def test_zip_plus_four_ignored():
    h1 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001-1234")
    h2 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    assert h1 == h2


def test_state_case_insensitive():
    h1 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    h2 = compute_canonical_hash("123 Main St", "Houston", "tx", "77001")
    assert h1 == h2


def test_city_case_insensitive():
    h1 = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    h2 = compute_canonical_hash("123 Main St", "HOUSTON", "TX", "77001")
    assert h1 == h2


def test_hash_is_64_chars():
    h = compute_canonical_hash("123 Main St", "Houston", "TX", "77001")
    assert len(h) == 64


def test_zip_normalization_none():
    assert normalize_zip(None) is None
    assert normalize_zip("") is None


def test_zip_short_returns_none():
    assert normalize_zip("770") is None
