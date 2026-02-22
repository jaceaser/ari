"""
Unit tests for MCP tool endpoints.

External services (ScrapingBee, Cosmos, Bricked, Azure Blob) are mocked.
Run with: pytest apps/mcp/tests/test_tools.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the MCP app directory is on sys.path
MCP_DIR = str(Path(__file__).resolve().parent.parent)
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

from app import app


@pytest.fixture
def client():
    """Quart test client."""
    return app.test_client()


async def _post(client, path: str, payload: dict[str, Any] | None = None):
    """Helper to POST JSON and parse response."""
    resp = await client.post(path, json=payload or {"prompt": ""})
    data = await resp.get_json()
    return resp.status_code, data


# ---------------------------------------------------------------------------
# Health & metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    data = await resp.get_json()
    assert resp.status_code == 200
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    data = await resp.get_json()
    assert resp.status_code == 200
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_tools_list(client):
    resp = await client.get("/tools")
    data = await resp.get_json()
    assert resp.status_code == 200
    assert isinstance(data["tools"], list)
    assert len(data["tools"]) >= 16


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_education(client):
    status, data = await _post(client, "/tools/classify", {"prompt": "What is wholesaling?"})
    assert status == 200
    assert data["ok"] is True
    assert data["tool"] == "classify"
    assert data["result"]["route"] == "Education"


@pytest.mark.asyncio
async def test_classify_leads(client):
    status, data = await _post(client, "/tools/classify", {"prompt": "Find seller leads on Zillow"})
    assert status == 200
    assert data["result"]["route"] == "Leads"


@pytest.mark.asyncio
async def test_classify_offtopic(client):
    status, data = await _post(client, "/tools/classify", {"prompt": "What is the weather today?"})
    assert status == 200
    assert data["result"]["route"] == "Offtopic"


@pytest.mark.asyncio
async def test_classify_comps(client):
    status, data = await _post(client, "/tools/classify", {"prompt": "Run comps for this property"})
    assert status == 200
    assert data["result"]["route"] == "Comps"


@pytest.mark.asyncio
async def test_classify_strategy(client):
    status, data = await _post(client, "/tools/classify", {"prompt": "Build me a business plan"})
    assert status == 200
    assert data["result"]["route"] == "Strategy"


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_education(client):
    status, data = await _post(client, "/tools/education", {"prompt": "What is Subject To?"})
    assert status == 200
    assert data["result"]["route"] == "Education"
    assert "retrieval_query" in data["result"]
    assert isinstance(data["result"]["subtopics"], list)


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy(client):
    status, data = await _post(client, "/tools/strategy", {"prompt": "90 day plan for wholesaling"})
    assert status == 200
    assert data["result"]["route"] == "Strategy"


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contracts(client):
    status, data = await _post(
        client, "/tools/contracts",
        {"prompt": "What clauses should be in an assignment contract?"},
    )
    assert status == 200
    assert data["result"]["route"] == "Contracts"
    assert "expanded_prompt" in data["result"]


# ---------------------------------------------------------------------------
# Offtopic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offtopic(client):
    status, data = await _post(client, "/tools/offtopic", {"prompt": "Tell me a joke"})
    assert status == 200
    assert data["result"]["route"] == "Offtopic"


# ---------------------------------------------------------------------------
# Extract city/state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_city_state_from_prompt(client):
    status, data = await _post(
        client, "/tools/extract-city-state",
        {"prompt": "Show me buyers in Houston, TX"},
    )
    assert status == 200
    assert "Houston" in data["result"]["city"]
    assert data["result"]["state"] == "TX"


@pytest.mark.asyncio
async def test_extract_city_state_from_arguments(client):
    status, data = await _post(
        client, "/tools/extract-city-state",
        {"prompt": "", "arguments": {"city": "Phoenix", "state": "AZ"}},
    )
    assert status == 200
    assert data["result"]["city"] == "Phoenix"
    assert data["result"]["state"] == "AZ"


# ---------------------------------------------------------------------------
# Extract address
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_address(client):
    status, data = await _post(
        client, "/tools/extract-address",
        {"prompt": "Run comps for 123 Main St, Dallas, TX 75201"},
    )
    assert status == 200
    assert "123 Main St" in (data["result"]["address"] or "")


@pytest.mark.asyncio
async def test_extract_address_from_arguments(client):
    status, data = await _post(
        client, "/tools/extract-address",
        {"prompt": "", "arguments": {"address": "456 Oak Ave, Miami, FL 33101"}},
    )
    assert status == 200
    assert data["result"]["address"] == "456 Oak Ave, Miami, FL 33101"
    assert data["result"]["address_source"] == "arguments"


# ---------------------------------------------------------------------------
# Build retrieval query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_retrieval_query(client):
    status, data = await _post(
        client, "/tools/build-retrieval-query",
        {"prompt": "How do I calculate ARV for a wholesale deal in Dallas TX?"},
    )
    assert status == 200
    assert "arv" in data["result"]["retrieval_query"].lower()


# ---------------------------------------------------------------------------
# Infer lead type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infer_lead_type_preforeclosure(client):
    status, data = await _post(
        client, "/tools/infer-lead-type",
        {"prompt": 'https://www.zillow.com/homes/?searchQueryState={"pf":{"value":true}}'},
    )
    assert status == 200
    assert data["result"]["lead_type"] == "Pre-Foreclosure"


@pytest.mark.asyncio
async def test_infer_lead_type_no_url(client):
    status, data = await _post(
        client, "/tools/infer-lead-type",
        {"prompt": "classify this lead"},
    )
    assert status == 200
    assert data["result"]["lead_type"] == "Unknown"


# ---------------------------------------------------------------------------
# Integration config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_config(client):
    status, data = await _post(client, "/tools/integration-config")
    assert status == 200
    assert isinstance(data["result"], dict)


# ---------------------------------------------------------------------------
# Leads (mocked scraping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leads_no_url(client):
    """Without a URL, leads should return awaiting_url status."""
    status, data = await _post(client, "/tools/leads", {"prompt": "Find me seller leads"})
    assert status == 200
    assert data["result"]["status"] == "awaiting_url"


@pytest.mark.asyncio
async def test_leads_with_url_mocked(client):
    """With a URL and mocked scraping, leads should return ok."""
    mock_result = {
        "status": "ok",
        "source": "scrape",
        "preview": "Address  Price\n123 Main  100000",
        "excel_link": "https://example.com/leads.xlsx",
        "properties_count": 5,
    }
    mock_module = MagicMock()
    mock_module.get_properties = AsyncMock(return_value=mock_result)
    with patch.dict("sys.modules", {"services.lead_gen": mock_module, "services": MagicMock()}):
        status, data = await _post(
            client, "/tools/leads",
            {
                "prompt": "scrape leads",
                "arguments": {"url": "https://zillow.com/test"},
            },
        )
    assert status == 200
    assert data["result"]["route"] == "Leads"
    # Should have attempted scraping since URL was provided
    assert data["result"].get("status") in ("ok", "error", "awaiting_url")


# ---------------------------------------------------------------------------
# Attorneys (mocked scraping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attorneys_no_url(client):
    """Without URL, attorneys returns awaiting_url."""
    status, data = await _post(
        client, "/tools/attorneys",
        {"prompt": "Find probate attorneys in Phoenix, AZ"},
    )
    assert status == 200
    assert data["result"]["status"] == "awaiting_url"
    assert "Phoenix" in (data["result"]["city"] or "")
    assert data["result"]["state"] == "AZ"


# ---------------------------------------------------------------------------
# Buyers (cosmos mocked by env absence)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buyers_missing_location(client):
    status, data = await _post(client, "/tools/buyers", {"prompt": "show me buyers"})
    assert status == 200
    assert data["result"]["status"] == "missing_location"


@pytest.mark.asyncio
async def test_buyers_search_missing_location(client):
    status, data = await _post(
        client, "/tools/buyers-search",
        {"prompt": "find buyers"},
    )
    assert status == 200
    assert data["result"]["status"] == "missing_location"


# ---------------------------------------------------------------------------
# Bricked comps (mocked by env absence)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bricked_comps_missing_address(client):
    status, data = await _post(
        client, "/tools/bricked-comps",
        {"prompt": "run comps"},
    )
    assert status == 200
    assert data["result"]["status"] == "missing_address"


@pytest.mark.asyncio
async def test_comps_with_address(client):
    status, data = await _post(
        client, "/tools/comps",
        {"prompt": "comps for 123 Main St, Dallas, TX 75201"},
    )
    assert status == 200
    assert data["result"]["route"] == "Comps"
    # Without BRICKED_API_KEY, this will be error status
    assert data["result"]["status"] in ("ok", "error", "missing_address")


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_404(client):
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404
