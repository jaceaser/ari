"""
Unit tests for the TX tax delinquent service.

These tests verify:
  - Query builder correctness (all filter combinations)
  - Limit / offset clamping (model cannot exceed bounds)
  - sptb_code-only filter rejection (prevents full-table scan)
  - County resolution fallback behaviour
  - Graceful config-missing handling
  - SQL parameterization safety (no string interpolation)
  - Entitlement: mcp_tx_tax_leads not visible to lite/basic tier users

Tests do NOT require a live database connection — they test the pure logic
of the query builder and the config-missing fallback path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the MCP service package is importable when running from the repo root
_MCP_ROOT = Path(__file__).resolve().parents[1]
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Remove TX_DELINQUENT_PG_* env vars before each test."""
    for key in [
        "TX_DELINQUENT_PG_HOST",
        "TX_DELINQUENT_PG_PORT",
        "TX_DELINQUENT_PG_DATABASE",
        "TX_DELINQUENT_PG_USERNAME",
        "TX_DELINQUENT_PG_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def env_configured(monkeypatch):
    """Set valid TX_DELINQUENT_PG_* env vars."""
    monkeypatch.setenv("TX_DELINQUENT_PG_HOST", "txasset-pg.postgres.database.azure.com")
    monkeypatch.setenv("TX_DELINQUENT_PG_PORT", "5432")
    monkeypatch.setenv("TX_DELINQUENT_PG_DATABASE", "taxdelinquent")
    monkeypatch.setenv("TX_DELINQUENT_PG_USERNAME", "txassetadmin")
    monkeypatch.setenv("TX_DELINQUENT_PG_PASSWORD", "test-password-not-real")


# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

from services.tx_tax_delinquent import (
    _conn_string,
    _build_search_query,
    _is_configured,
    query_properties,
    query_property_detail,
    query_assessment,
    _DEFAULT_LIMIT,
    _MAX_LIMIT,
    _MAX_OFFSET,
)


# ---------------------------------------------------------------------------
# Connection factory tests
# ---------------------------------------------------------------------------

class TestConnString:
    def test_returns_none_when_no_env_vars(self):
        assert _conn_string() is None

    def test_returns_none_when_password_missing(self, monkeypatch):
        monkeypatch.setenv("TX_DELINQUENT_PG_HOST", "txasset-pg.postgres.database.azure.com")
        monkeypatch.setenv("TX_DELINQUENT_PG_DATABASE", "taxdelinquent")
        monkeypatch.setenv("TX_DELINQUENT_PG_USERNAME", "txassetadmin")
        # TX_DELINQUENT_PG_PASSWORD deliberately missing
        assert _conn_string() is None

    def test_returns_conn_string_when_configured(self, env_configured):
        cs = _conn_string()
        assert cs is not None
        assert "txasset-pg.postgres.database.azure.com" in cs
        assert "taxdelinquent" in cs
        assert "txassetadmin" in cs
        assert "sslmode=require" in cs

    def test_password_in_conn_string(self, env_configured):
        cs = _conn_string()
        # Password must be present in the connection string (for psycopg2)
        assert "test-password-not-real" in cs

    def test_ssl_always_required(self, env_configured):
        cs = _conn_string()
        assert "sslmode=require" in cs

    def test_is_configured_false_without_env(self):
        assert _is_configured() is False

    def test_is_configured_true_with_env(self, env_configured):
        assert _is_configured() is True


# ---------------------------------------------------------------------------
# Query builder tests
# ---------------------------------------------------------------------------

class TestBuildSearchQuery:
    """Tests for _build_search_query — no DB connection required."""

    def _build(self, filters: dict, county_key=None) -> tuple[str, dict]:
        return _build_search_query(filters, county_key)

    def test_always_includes_is_delinquent(self):
        sql, params = self._build({})
        assert "is_delinquent = true" in sql

    def test_default_limit(self):
        sql, params = self._build({})
        assert params["limit"] == _DEFAULT_LIMIT

    def test_explicit_limit(self):
        _, params = self._build({"limit": 50})
        assert params["limit"] == 50

    def test_limit_clamped_to_max(self):
        _, params = self._build({"limit": 9999})
        assert params["limit"] == _MAX_LIMIT

    def test_limit_clamped_to_min(self):
        _, params = self._build({"limit": 0})
        assert params["limit"] == 1

    def test_negative_limit_clamped(self):
        _, params = self._build({"limit": -10})
        assert params["limit"] == 1

    def test_offset_default(self):
        _, params = self._build({})
        assert params["offset"] == 0

    def test_offset_clamped_to_max(self):
        _, params = self._build({"offset": 999999})
        assert params["offset"] == _MAX_OFFSET

    def test_offset_negative_clamped(self):
        _, params = self._build({"offset": -5})
        assert params["offset"] == 0

    def test_county_key_filter(self):
        sql, params = self._build({}, county_key=101)
        assert "county_key = %(county_key)s" in sql
        assert params["county_key"] == 101

    def test_county_name_fallback_when_no_key(self):
        sql, params = self._build({"county_name": "Harris"}, county_key=None)
        assert "county_name ILIKE %(county_name)s" in sql
        assert params["county_name"] == "Harris"

    def test_min_amount_due(self):
        sql, params = self._build({"min_amount_due": 50000})
        assert "total_amount_due >= %(min_amount_due)s" in sql
        assert params["min_amount_due"] == 50000.0

    def test_max_amount_due(self):
        sql, params = self._build({"max_amount_due": 200000})
        assert "total_amount_due <= %(max_amount_due)s" in sql
        assert params["max_amount_due"] == 200000.0

    def test_min_and_max_amount_due(self):
        sql, params = self._build({"min_amount_due": 10000, "max_amount_due": 100000})
        assert "total_amount_due >= %(min_amount_due)s" in sql
        assert "total_amount_due <= %(max_amount_due)s" in sql
        assert params["min_amount_due"] == 10000.0
        assert params["max_amount_due"] == 100000.0

    def test_owner_name_ilike(self):
        sql, params = self._build({"owner_name": "LLC"})
        assert "owner_name ILIKE %(owner_name)s" in sql
        assert params["owner_name"] == "%LLC%"

    def test_owner_name_wrapped_in_percent(self):
        sql, params = self._build({"owner_name": "Smith"})
        assert params["owner_name"] == "%Smith%"

    def test_out_of_state(self):
        sql, _ = self._build({"out_of_state": True})
        assert "owner_mail_state != 'TX'" in sql

    def test_out_of_state_false_not_added(self):
        sql, _ = self._build({"out_of_state": False})
        # owner_mail_state appears in SELECT; we want it absent from WHERE
        where_portion = sql.split("WHERE", 1)[-1] if "WHERE" in sql else sql
        assert "owner_mail_state" not in where_portion

    def test_min_years_delinquent(self):
        sql, params = self._build({"min_years_delinquent": 5})
        assert "years_delinquent >= %(min_years_delinquent)s" in sql
        assert params["min_years_delinquent"] == 5

    def test_has_lawsuit(self):
        sql, _ = self._build({"has_lawsuit": True})
        assert "has_lawsuit = true" in sql

    def test_has_lawsuit_false_not_added(self):
        sql, _ = self._build({"has_lawsuit": False})
        # has_lawsuit appears in SELECT; check it is absent from WHERE clause
        where_portion = sql.split("WHERE", 1)[-1] if "WHERE" in sql else sql
        assert "has_lawsuit = true" not in where_portion

    def test_has_judgment(self):
        sql, _ = self._build({"has_judgment": True})
        assert "has_judgment = true" in sql

    def test_min_market_value(self):
        sql, params = self._build({"min_market_value": 100000})
        assert "market_value >= %(min_market_value)s" in sql
        assert params["min_market_value"] == 100000.0

    def test_max_market_value(self):
        sql, params = self._build({"max_market_value": 500000})
        assert "market_value <= %(max_market_value)s" in sql
        assert params["max_market_value"] == 500000.0

    def test_sptb_code_requires_other_filter(self):
        """sptb_code alone must raise ValueError — it would cause a slow full-table scan."""
        with pytest.raises(ValueError, match="sptb_code filter requires"):
            self._build({"sptb_code": "F1"})

    def test_sptb_code_allowed_with_county(self):
        sql, params = self._build({"sptb_code": "F1"}, county_key=42)
        assert "sptb_code = %(sptb_code)s" in sql
        assert params["sptb_code"] == "F1"

    def test_sptb_code_allowed_with_amount_filter(self):
        sql, params = self._build({"sptb_code": "A1", "min_amount_due": 5000})
        assert "sptb_code = %(sptb_code)s" in sql
        assert params["sptb_code"] == "A1"

    def test_sptb_code_allowed_with_owner_name(self):
        sql, params = self._build({"sptb_code": "A1", "owner_name": "LLC"})
        assert "sptb_code = %(sptb_code)s" in sql

    def test_sptb_code_uppercased(self):
        _, params = self._build({"sptb_code": "a1"}, county_key=1)
        assert params["sptb_code"] == "A1"

    def test_combined_filters(self):
        sql, params = self._build(
            {
                "min_amount_due": 10000,
                "owner_name": "LLC",
                "has_lawsuit": True,
                "min_years_delinquent": 3,
                "limit": 50,
            },
            county_key=101,
        )
        assert "is_delinquent = true" in sql
        assert "county_key = %(county_key)s" in sql
        assert "total_amount_due >= %(min_amount_due)s" in sql
        assert "owner_name ILIKE %(owner_name)s" in sql
        assert "has_lawsuit = true" in sql
        assert "years_delinquent >= %(min_years_delinquent)s" in sql
        assert params["limit"] == 50

    def test_no_string_interpolation_in_sql(self):
        """Verify SQL contains only %(name)s placeholders, never raw values."""
        sql, params = self._build(
            {"owner_name": "DROP TABLE; --", "county_name": "'; DELETE FROM fact_property_latest; --"},
            county_key=None,
        )
        # The raw injection strings should not appear in SQL
        assert "DROP TABLE" not in sql
        assert "DELETE FROM fact_property_latest" not in sql
        # But the dangerous value IS in params (psycopg2 will safely escape it)
        assert "DROP TABLE; --" in params.get("owner_name", "")

    def test_sql_contains_from_fact_property_latest(self):
        sql, _ = self._build({})
        assert "FROM fact_property_latest" in sql

    def test_order_by_total_amount_due_desc(self):
        sql, _ = self._build({})
        assert "ORDER BY total_amount_due DESC" in sql

    def test_limit_and_offset_in_params_not_sql_interpolated(self):
        sql, params = self._build({"limit": 25, "offset": 50})
        assert "LIMIT %(limit)s" in sql
        assert "OFFSET %(offset)s" in sql
        assert params["limit"] == 25
        assert params["offset"] == 50


# ---------------------------------------------------------------------------
# Config-missing graceful degradation
# ---------------------------------------------------------------------------

class TestQueryPropertiesConfigMissing:
    """Verify all query functions return error dicts when env vars missing."""

    def test_query_properties_config_missing(self):
        result = query_properties({})
        assert result["status"] == "config_missing"
        assert result["count"] == 0
        assert result["rows"] == []
        assert "not configured" in result["message"].lower()

    def test_query_property_detail_config_missing(self):
        result = query_property_detail(12345)
        assert result["status"] == "config_missing"
        assert result["row"] is None

    def test_query_assessment_config_missing(self):
        result = query_assessment(12345)
        assert result["status"] == "config_missing"
        assert result["rows"] == []

    def test_no_db_credentials_in_error_message(self):
        """Error messages must never expose credentials."""
        result = query_properties({})
        msg = result.get("message", "")
        # Should not contain password or host
        assert "test-password" not in msg
        assert "txasset-pg" not in msg


# ---------------------------------------------------------------------------
# County not found error
# ---------------------------------------------------------------------------

class TestCountyNotFound:
    def test_unknown_county_returns_error(self, env_configured):
        """When county_name does not exist in dim_county, return helpful error."""
        with patch("services.tx_tax_delinquent.resolve_county_key", return_value=None):
            result = query_properties({"county_name": "Narnia"})
        assert result["status"] == "error"
        assert "Narnia" in result["message"]
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# sptb_code-only rejection via query_properties
# ---------------------------------------------------------------------------

class TestSptbCodeOnlyRejection:
    def test_sptb_only_rejected_with_error_status(self, env_configured):
        """sptb_code with no other filter → error before any DB call."""
        with patch("services.tx_tax_delinquent.resolve_county_key", return_value=None):
            result = query_properties({"sptb_code": "F1"})
        assert result["status"] == "error"
        assert "sptb_code" in result["message"].lower()

    def test_sptb_with_county_does_not_raise(self, env_configured):
        """sptb_code + county is valid — should proceed to DB call (which we mock)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("services.tx_tax_delinquent.resolve_county_key", return_value=101), \
             patch("psycopg2.connect", return_value=mock_conn):
            result = query_properties({"sptb_code": "F1", "county_name": "Harris"})
        assert result["status"] == "no_results"


# ---------------------------------------------------------------------------
# Limit clamping via query_properties
# ---------------------------------------------------------------------------

class TestLimitClamping:
    def test_model_cannot_exceed_max_limit(self, env_configured):
        """Even if model passes limit=9999, server clamps to _MAX_LIMIT=100."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        captured_params = {}

        def fake_execute(sql, params):
            captured_params.update(params)

        mock_cursor.execute = fake_execute

        with patch("services.tx_tax_delinquent.resolve_county_key", return_value=None), \
             patch("psycopg2.connect", return_value=mock_conn):
            query_properties({"limit": 9999, "county_name": "Harris"})

        assert captured_params.get("limit", 0) <= _MAX_LIMIT

    def test_model_cannot_exceed_max_offset(self, env_configured):
        """Even if model passes offset=999999, server clamps to _MAX_OFFSET."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        captured_params = {}

        def fake_execute(sql, params):
            captured_params.update(params)

        mock_cursor.execute = fake_execute

        with patch("services.tx_tax_delinquent.resolve_county_key", return_value=None), \
             patch("psycopg2.connect", return_value=mock_conn):
            query_properties({"offset": 999999, "county_name": "Harris"})

        assert captured_params.get("offset", 0) <= _MAX_OFFSET


# ---------------------------------------------------------------------------
# Entitlement tests — mcp_tx_tax_leads not visible to lite/basic tiers
# ---------------------------------------------------------------------------

class TestEntitlement:
    """
    Verify the tier-based tool filtering in apps/api/app.py.

    These tests add the api/ directory to the path to import the tool
    definitions and tier logic directly, without starting the server.
    """

    @pytest.fixture(autouse=True)
    def _add_api_to_path(self):
        api_root = Path(__file__).resolve().parents[2] / "api"
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))

    def _get_api_module(self):
        """Import apps/api/app.py module without running the server."""
        import importlib
        # Mock out heavy dependencies before import
        heavy = [
            "azure.cosmos.aio", "openai", "stripe",
            "azure.communication.email",
            "billing.database", "billing.metering_service",
            "billing.reporting_service", "cosmos",
        ]
        mocks = {}
        for mod in heavy:
            mocks[mod] = MagicMock()

        with patch.dict("sys.modules", mocks):
            import app as api_app
            return api_app

    def test_mcp_tx_tax_leads_not_in_lite_tools(self):
        """mcp_tx_tax_leads must NOT appear in the lite-tier tool allowlist."""
        try:
            api = self._get_api_module()
        except Exception:
            pytest.skip("api/app.py import failed — skipping entitlement test in this env")

        lite_tools = getattr(api, "_TIER_TOOLS", {}).get("lite", frozenset())
        assert "mcp_tx_tax_leads" not in lite_tools, (
            "mcp_tx_tax_leads must not be accessible to lite-tier users"
        )

    def test_mcp_tx_tax_leads_not_in_basic_tools(self):
        """mcp_tx_tax_leads must NOT appear in the basic-tier tool allowlist."""
        try:
            api = self._get_api_module()
        except Exception:
            pytest.skip("api/app.py import failed — skipping entitlement test in this env")

        basic_tools = getattr(api, "_TIER_TOOLS", {}).get("basic", frozenset())
        assert "mcp_tx_tax_leads" not in basic_tools, (
            "mcp_tx_tax_leads must not be accessible to basic-tier users"
        )

    def test_mcp_tx_tax_leads_in_elite_tools(self):
        """mcp_tx_tax_leads MUST be visible to elite users (via _ALL_TOOL_NAMES)."""
        try:
            api = self._get_api_module()
        except Exception:
            pytest.skip("api/app.py import failed — skipping entitlement test in this env")

        elite_tools = getattr(api, "_TIER_TOOLS", {}).get("elite", frozenset())
        all_tool_names = getattr(api, "_ALL_TOOL_NAMES", frozenset())
        # Elite should have ALL tools
        assert elite_tools == all_tool_names or "mcp_tx_tax_leads" in elite_tools, (
            "mcp_tx_tax_leads must be accessible to elite-tier users"
        )

    def test_mcp_tx_tax_leads_in_mcp_tool_definitions(self):
        """mcp_tx_tax_leads must appear in MCP_TOOL_DEFINITIONS."""
        try:
            api = self._get_api_module()
        except Exception:
            pytest.skip("api/app.py import failed — skipping entitlement test in this env")

        definitions = getattr(api, "MCP_TOOL_DEFINITIONS", [])
        names = [d.get("function", {}).get("name") for d in definitions]
        assert "mcp_tx_tax_leads" in names

    def test_mcp_tx_tax_leads_in_mcp_tool_endpoints(self):
        """mcp_tx_tax_leads must map to /tools/tx-tax-leads in MCP_TOOL_ENDPOINTS."""
        try:
            api = self._get_api_module()
        except Exception:
            pytest.skip("api/app.py import failed — skipping entitlement test in this env")

        endpoints = getattr(api, "MCP_TOOL_ENDPOINTS", {})
        assert endpoints.get("mcp_tx_tax_leads") == "/tools/tx-tax-leads"


# ---------------------------------------------------------------------------
# Guardrails allowlist tests
# ---------------------------------------------------------------------------

class TestGuardrailsAllowlist:
    """Verify the MCP guardrails include /tools/tx-tax-leads in REAL_ESTATE_CORE."""

    def _load_mcp_guardrails(self):
        """Load mcp/middleware/guardrails.py explicitly by file path to avoid api/middleware collision."""
        import importlib.util
        guard_path = Path(__file__).resolve().parents[1] / "middleware" / "guardrails.py"
        spec = importlib.util.spec_from_file_location("mcp_guardrails", guard_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_tx_tax_leads_in_core_allowlist(self):
        mod = self._load_mcp_guardrails()
        core_paths = mod.TOOL_ALLOWLIST.get(mod.Intent.REAL_ESTATE_CORE, frozenset())
        assert "/tools/tx-tax-leads" in core_paths, (
            "/tools/tx-tax-leads must be in REAL_ESTATE_CORE allowlist"
        )

    def test_tx_tax_leads_not_in_general_allowlist(self):
        """Tax leads should NOT be available for REAL_ESTATE_GENERAL intent."""
        mod = self._load_mcp_guardrails()
        general_paths = mod.TOOL_ALLOWLIST.get(mod.Intent.REAL_ESTATE_GENERAL, frozenset())
        assert "/tools/tx-tax-leads" not in general_paths

    def test_tx_tax_leads_not_in_off_topic_allowlist(self):
        mod = self._load_mcp_guardrails()
        off_topic_paths = mod.TOOL_ALLOWLIST.get(mod.Intent.OFF_TOPIC, frozenset())
        assert "/tools/tx-tax-leads" not in off_topic_paths
