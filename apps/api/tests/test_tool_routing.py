"""
Tests for MCP tool routing signals.

These tests verify that tool descriptions and the orchestration prompt contain
the correct signals for the model to route requests to the right tool.
They do NOT test the LLM's decision — they test that the definitions we feed
the model are unambiguous and internally consistent.
"""

from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import MCP_TOOL_DEFINITIONS, MCP_TOOL_ENDPOINTS, _ORCHESTRATION_SYSTEM_PROMPT, _CLASSIFY_KEYWORDS, _ROUTE_TOOL_HINT, AZURE_OPENAI_CLASSIFICATION_SYSTEM_MESSAGE


def _desc(name: str) -> str:
    tool = next((t for t in MCP_TOOL_DEFINITIONS if t["function"]["name"] == name), None)
    assert tool is not None, f"Tool {name!r} not found in MCP_TOOL_DEFINITIONS"
    return tool["function"]["description"]


def _params(name: str) -> dict:
    tool = next((t for t in MCP_TOOL_DEFINITIONS if t["function"]["name"] == name), None)
    assert tool is not None
    return tool["function"]["parameters"]["properties"]


# ---------------------------------------------------------------------------
# mcp_leads_context — must NOT claim ownership of Texas tax delinquent
# ---------------------------------------------------------------------------

class TestLeadsContextDescription:
    def test_excludes_texas_tax_delinquent_at_start(self):
        """Exclusion must be at the START of the description so the model sees it first."""
        desc = _desc("mcp_leads_context")
        first_sentence = desc.split(".")[0].lower()
        assert "not for texas tax delinquent" in first_sentence or \
               "mcp_tx_tax_leads" in first_sentence, (
            "mcp_leads_context description must open with the Texas tax delinquent exclusion"
        )

    def test_mentions_tx_tax_leads_as_alternative(self):
        desc = _desc("mcp_leads_context")
        assert "mcp_tx_tax_leads" in desc

    def test_does_not_claim_texas_tax_delinquent(self):
        desc = _desc("mcp_leads_context").lower()
        # Should not say "use this for tax delinquent in Texas" or similar
        assert "tax delinquent in texas" not in desc
        assert "texas tax delinquent" not in desc or "not" in desc[:desc.index("texas tax delinquent")]


# ---------------------------------------------------------------------------
# mcp_tx_tax_leads — must clearly own Texas tax delinquent
# ---------------------------------------------------------------------------

class TestTxTaxLeadsDescription:
    def test_opens_with_texas_tax_delinquent_ownership(self):
        desc = _desc("mcp_tx_tax_leads")
        assert "texas" in desc[:80].lower(), (
            "mcp_tx_tax_leads description should mention Texas in the first 80 chars"
        )

    def test_mentions_not_zillow(self):
        desc = _desc("mcp_tx_tax_leads").lower()
        assert "not zillow" in desc or "zillow" not in desc or "appraisal" in desc

    def test_has_county_name_param(self):
        params = _params("mcp_tx_tax_leads")
        assert "county_name" in params

    def test_has_city_param(self):
        params = _params("mcp_tx_tax_leads")
        assert "city" in params

    def test_has_owner_name_param_with_entity_examples(self):
        params = _params("mcp_tx_tax_leads")
        assert "owner_name" in params
        desc = params["owner_name"]["description"].upper()
        for keyword in ("LLC", "TRUST", "ESTATE"):
            assert keyword in desc, f"owner_name description should mention {keyword}"

    def test_excludes_non_texas(self):
        desc = _desc("mcp_tx_tax_leads").lower()
        assert "non-texas" in desc or "not for non-texas" in desc or "mcp_leads_context" in desc


# ---------------------------------------------------------------------------
# Orchestration prompt — should be short and principle-based, not a rule tree
# ---------------------------------------------------------------------------

class TestOrchestrationPrompt:
    def test_prompt_is_concise(self):
        """Prompt should not be a giant keyword decision tree."""
        lines = [l for l in _ORCHESTRATION_SYSTEM_PROMPT.splitlines() if l.strip()]
        assert len(lines) <= 15, (
            f"Orchestration prompt is {len(lines)} lines — keep it short and let tool descriptions route"
        )

    def test_mentions_tx_geography_hint(self):
        assert "county_name" in _ORCHESTRATION_SYSTEM_PROMPT or "county" in _ORCHESTRATION_SYSTEM_PROMPT.lower()

    def test_no_hardcoded_city_county_table(self):
        """Should not have a hardcoded city→county lookup table — the model knows geography."""
        prompt = _ORCHESTRATION_SYSTEM_PROMPT
        # If it has 5+ Texas city names it's probably a lookup table
        tx_cities = ["McAllen", "Hidalgo", "Pasadena", "Pearland", "Pflugerville", "McLennan"]
        found = sum(1 for city in tx_cities if city in prompt)
        assert found < 3, (
            f"Orchestration prompt has {found} hardcoded Texas cities — remove the lookup table"
        )


# ---------------------------------------------------------------------------
# Pre-classifier keyword fast-path — the real routing bottleneck
# ---------------------------------------------------------------------------

class TestClassifyKeywords:
    def test_tax_delinquent_not_in_leads(self):
        """'tax delinquent' must NOT be in Leads keywords — it fires mcp_leads_context."""
        leads_kws = _CLASSIFY_KEYWORDS.get("Leads", set())
        assert "tax delinquent" not in leads_kws, (
            "'tax delinquent' in Leads keywords causes all TX tax queries to route to mcp_leads_context"
        )

    def test_tax_lien_not_in_leads(self):
        leads_kws = _CLASSIFY_KEYWORDS.get("Leads", set())
        assert "tax lien" not in leads_kws

    def test_tx_tax_leads_route_exists(self):
        assert "TxTaxLeads" in _CLASSIFY_KEYWORDS, (
            "TxTaxLeads route must exist in _CLASSIFY_KEYWORDS"
        )

    def test_tx_tax_leads_keywords_cover_tax_delinquent(self):
        kws = _CLASSIFY_KEYWORDS.get("TxTaxLeads", set())
        assert "tax delinquent" in kws

    def test_tx_tax_leads_hint_routes_to_correct_tool(self):
        hint = _ROUTE_TOOL_HINT.get("TxTaxLeads", "")
        assert "mcp_tx_tax_leads" in hint, (
            "TxTaxLeads route hint must tell the model to call mcp_tx_tax_leads"
        )
        assert "mcp_leads_context" not in hint

    def test_leads_hint_routes_to_leads_context(self):
        hint = _ROUTE_TOOL_HINT.get("Leads", "")
        assert "mcp_leads_context" in hint

    def test_gpt_mini_classification_message_includes_tx_tax_leads(self):
        """gpt-5-mini fallback must know TxTaxLeads exists."""
        assert "TxTaxLeads" in AZURE_OPENAI_CLASSIFICATION_SYSTEM_MESSAGE

    def test_gpt_mini_classification_message_describes_tx_tax_leads(self):
        msg = AZURE_OPENAI_CLASSIFICATION_SYSTEM_MESSAGE.lower()
        assert "texas" in msg, "gpt-5-mini system message should explain TxTaxLeads covers Texas"

    def test_tie_between_tx_and_leads_resolves_to_tx(self):
        """'show me tax delinquent leads in houston' scores 1 for both — TxTaxLeads must win."""
        prompt = "show me tax delinquent leads in houston"
        text = prompt.lower()
        scores = {route: sum(1 for kw in kws if kw in text) for route, kws in _CLASSIFY_KEYWORDS.items()}
        best = max(scores.values(), default=0)
        winners = [r for r, s in scores.items() if s == best]
        # Apply the tie-break rule
        if set(winners) == {"TxTaxLeads", "Leads"}:
            winners = ["TxTaxLeads"]
        assert winners == ["TxTaxLeads"], f"Expected TxTaxLeads to win tie, got {winners}"


# ---------------------------------------------------------------------------
# Tool registry consistency
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_tx_tax_leads_in_endpoints(self):
        assert "mcp_tx_tax_leads" in MCP_TOOL_ENDPOINTS
        assert MCP_TOOL_ENDPOINTS["mcp_tx_tax_leads"] == "/tools/tx-tax-leads"

    def test_tx_tax_leads_in_definitions(self):
        names = [t["function"]["name"] for t in MCP_TOOL_DEFINITIONS]
        assert "mcp_tx_tax_leads" in names

    def test_leads_context_in_endpoints(self):
        assert "mcp_leads_context" in MCP_TOOL_ENDPOINTS

    def test_no_duplicate_tool_names(self):
        names = [t["function"]["name"] for t in MCP_TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), "Duplicate tool names in MCP_TOOL_DEFINITIONS"
