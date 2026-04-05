"""
Tool pricing configuration for ARI's MCP and local tools.

cost_type="flat"     — fixed USD cost per invocation (current default for all tools)
cost_type="variable" — reserved for future use (e.g. per-result pricing on lead runs)

Costs reflect upstream charges: ScrapingBee API, third-party data APIs, Azure Blob
compute. Zero-cost tools are knowledge-base lookups with no third-party spend.

Key principle: unknown tools return Decimal("0") with a logged warning so a
missing entry never crashes a user request.
"""
import logging
from decimal import Decimal
from typing import Literal, TypedDict

logger = logging.getLogger("ari.billing.tool_pricing")


class ToolPricing(TypedDict):
    cost_type: Literal["flat", "variable"]
    cost: Decimal     # flat: cost per call; variable: base/minimum cost
    description: str


# Registry keyed by tool name as it appears in MCP_TOOL_ENDPOINTS (app.py)
# and in local tool dispatch (generate_document, mcp_stack_lists).
TOOL_PRICING: dict[str, ToolPricing] = {
    # ── MCP tools (proxied via HTTP to apps/mcp) ─────────────────────────────

    # High-cost: involves live ScrapingBee scraping
    "mcp_leads_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.100000"),
        description="Lead generation — Zillow/ScrapingBee property scraping",
    ),
    "mcp_buyers_search": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.050000"),
        description="Cash buyer database search",
    ),

    # Medium-cost: third-party comp/ARV data
    "mcp_comps_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.050000"),
        description="Comparable property analysis",
    ),
    "mcp_bricked_comps": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.050000"),
        description="Bricked comps — ARV calculation",
    ),
    "mcp_buyers_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.050000"),
        description="Buyer context retrieval",
    ),

    # Low-cost: cached directory / knowledge-base lookups
    "mcp_attorneys_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.010000"),
        description="Real estate attorney directory lookup",
    ),

    # Zero-cost: local knowledge-base, no third-party spend
    "mcp_strategy_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Investment strategy context retrieval",
    ),
    "mcp_contracts_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Contract template retrieval",
    ),
    "mcp_education_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Real estate education content retrieval",
    ),
    "mcp_offtopic_context": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Off-topic deflection context",
    ),
    "mcp_classify_route": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Route classification",
    ),
    "mcp_extract_city_state": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="City/state extraction from prompt",
    ),
    "mcp_extract_address": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Address extraction from prompt",
    ),
    "mcp_build_retrieval_query": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Retrieval query builder",
    ),
    "mcp_infer_lead_type": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Lead type inference",
    ),
    "mcp_integration_config": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.000000"),
        description="Backend availability / integration config",
    ),

    # ── Local tools (no MCP proxy) ────────────────────────────────────────────

    "generate_document": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.010000"),
        description="DOCX generation + Azure Blob Storage upload",
    ),
    "mcp_stack_lists": ToolPricing(
        cost_type="flat",
        cost=Decimal("0.010000"),
        description="Property list stacking (overlap analysis) + Blob upload",
    ),
}


def get_tool_cost(tool_name: str) -> Decimal:
    """
    Return the estimated USD cost for one tool invocation.

    Returns Decimal("0") for unknown tools and logs a warning so pricing
    gaps are visible in logs without crashing anything.
    """
    pricing = TOOL_PRICING.get(tool_name)
    if pricing is None:
        logger.warning(
            "Unknown tool '%s' — no pricing data, cost recorded as $0.00. "
            "Add this tool to billing/tool_pricing.py.",
            tool_name,
        )
        return Decimal("0")
    return pricing["cost"]
