"""
Phase 1B tests — model and tool pricing.

Covers:
  - calculate_token_cost: known model, unknown model, zero tokens, large values,
    Decimal precision, no floating-point drift
  - get_tool_cost: known tool, unknown tool, zero-cost tool
  - Registry completeness: all ARI tools and models are registered
"""
from decimal import Decimal

import pytest


# ── calculate_token_cost ───────────────────────────────────────────────────────


class TestCalculateTokenCost:
    def test_known_model_returns_nonzero_cost(self):
        from billing.model_pricing import calculate_token_cost
        cost = calculate_token_cost("gpt-5.2-chat", input_tokens=1000, output_tokens=1000)
        assert cost > Decimal("0")

    def test_unknown_model_returns_zero(self):
        from billing.model_pricing import calculate_token_cost
        cost = calculate_token_cost("gpt-99-unknown", input_tokens=1000, output_tokens=500)
        assert cost == Decimal("0")

    def test_unknown_model_logs_warning(self, caplog):
        import logging
        from billing.model_pricing import calculate_token_cost
        with caplog.at_level(logging.WARNING, logger="ari.billing.model_pricing"):
            calculate_token_cost("mystery-model", input_tokens=100, output_tokens=100)
        assert "mystery-model" in caplog.text

    def test_zero_tokens_returns_zero(self):
        from billing.model_pricing import calculate_token_cost
        assert calculate_token_cost("gpt-5.2-chat", 0, 0) == Decimal("0")

    def test_zero_input_tokens_charges_only_output(self):
        from billing.model_pricing import calculate_token_cost
        from billing.model_pricing import MODEL_PRICING
        cost = calculate_token_cost("gpt-5.2-chat", input_tokens=0, output_tokens=1000)
        expected = MODEL_PRICING["gpt-5.2-chat"]["output_cost_per_1k"]
        assert cost == expected.quantize(Decimal("0.000001"))

    def test_zero_output_tokens_charges_only_input(self):
        from billing.model_pricing import calculate_token_cost
        from billing.model_pricing import MODEL_PRICING
        cost = calculate_token_cost("gpt-5.2-chat", input_tokens=1000, output_tokens=0)
        expected = MODEL_PRICING["gpt-5.2-chat"]["input_cost_per_1k"]
        assert cost == expected.quantize(Decimal("0.000001"))

    def test_returns_decimal_not_float(self):
        from billing.model_pricing import calculate_token_cost
        cost = calculate_token_cost("gpt-5.2-chat", 500, 500)
        assert isinstance(cost, Decimal)

    def test_precision_is_six_decimal_places(self):
        from billing.model_pricing import calculate_token_cost
        cost = calculate_token_cost("gpt-5.2-chat", 1, 1)
        # Quantized to 0.000001 — exponent should be -6
        assert cost == cost.quantize(Decimal("0.000001"))

    def test_large_token_count(self):
        from billing.model_pricing import calculate_token_cost
        # 1M input + 1M output — should not overflow or lose precision
        cost = calculate_token_cost("gpt-5.2-chat", 1_000_000, 1_000_000)
        assert cost > Decimal("0")
        assert isinstance(cost, Decimal)

    def test_no_float_drift_across_many_calls(self):
        """Summing many Decimal costs must not accumulate floating-point error."""
        from billing.model_pricing import calculate_token_cost
        total = sum(
            calculate_token_cost("gpt-5-mini", 100, 50)
            for _ in range(1000)
        )
        single = calculate_token_cost("gpt-5-mini", 100, 50)
        assert total == single * 1000

    def test_classification_model_cheaper_than_chat_model(self):
        from billing.model_pricing import calculate_token_cost
        chat_cost = calculate_token_cost("gpt-5.2-chat", 1000, 1000)
        mini_cost = calculate_token_cost("gpt-5-mini", 1000, 1000)
        assert mini_cost < chat_cost

    @pytest.mark.parametrize("model", ["gpt-5.2-chat", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"])
    def test_all_registered_models_return_positive_cost(self, model):
        from billing.model_pricing import calculate_token_cost
        cost = calculate_token_cost(model, input_tokens=1000, output_tokens=500)
        assert cost > Decimal("0"), f"Model '{model}' returned zero cost"


# ── get_tool_cost ──────────────────────────────────────────────────────────────


class TestGetToolCost:
    def test_high_cost_tool_returns_expected_value(self):
        from billing.tool_pricing import get_tool_cost
        cost = get_tool_cost("mcp_leads_context")
        assert cost == Decimal("0.100000")

    def test_zero_cost_tool_returns_zero(self):
        from billing.tool_pricing import get_tool_cost
        assert get_tool_cost("mcp_education_context") == Decimal("0")

    def test_unknown_tool_returns_zero(self):
        from billing.tool_pricing import get_tool_cost
        assert get_tool_cost("non_existent_tool_xyz") == Decimal("0")

    def test_unknown_tool_logs_warning(self, caplog):
        import logging
        from billing.tool_pricing import get_tool_cost
        with caplog.at_level(logging.WARNING, logger="ari.billing.tool_pricing"):
            get_tool_cost("mystery_tool")
        assert "mystery_tool" in caplog.text

    def test_returns_decimal(self):
        from billing.tool_pricing import get_tool_cost
        assert isinstance(get_tool_cost("mcp_leads_context"), Decimal)

    def test_local_tools_have_cost(self):
        from billing.tool_pricing import get_tool_cost
        assert get_tool_cost("generate_document") > Decimal("0")
        assert get_tool_cost("mcp_stack_lists") > Decimal("0")

    @pytest.mark.parametrize("tool", [
        "mcp_leads_context", "mcp_buyers_search", "mcp_comps_context",
        "mcp_bricked_comps", "mcp_attorneys_context", "mcp_strategy_context",
        "mcp_contracts_context", "mcp_education_context", "mcp_offtopic_context",
        "mcp_buyers_context", "mcp_classify_route", "mcp_extract_city_state",
        "mcp_extract_address", "mcp_build_retrieval_query", "mcp_infer_lead_type",
        "mcp_integration_config", "generate_document", "mcp_stack_lists",
    ])
    def test_all_ari_tools_are_registered(self, tool):
        from billing.tool_pricing import TOOL_PRICING
        assert tool in TOOL_PRICING, f"Tool '{tool}' missing from TOOL_PRICING registry"


# ── Registry completeness ──────────────────────────────────────────────────────


class TestRegistryCompleteness:
    def test_all_mcp_tool_endpoints_are_priced(self):
        """Every tool in app.py MCP_TOOL_ENDPOINTS must have a pricing entry."""
        from billing.tool_pricing import TOOL_PRICING
        # Sourced from app.py MCP_TOOL_ENDPOINTS
        mcp_tools = {
            "mcp_integration_config", "mcp_classify_route", "mcp_education_context",
            "mcp_comps_context", "mcp_bricked_comps", "mcp_leads_context",
            "mcp_attorneys_context", "mcp_strategy_context", "mcp_contracts_context",
            "mcp_buyers_context", "mcp_buyers_search", "mcp_extract_city_state",
            "mcp_extract_address", "mcp_offtopic_context", "mcp_build_retrieval_query",
            "mcp_infer_lead_type",
        }
        missing = mcp_tools - set(TOOL_PRICING)
        assert not missing, f"MCP tools missing from TOOL_PRICING: {missing}"

    def test_local_tools_are_priced(self):
        from billing.tool_pricing import TOOL_PRICING
        assert "generate_document" in TOOL_PRICING
        assert "mcp_stack_lists" in TOOL_PRICING

    def test_active_models_are_priced(self):
        """Both deployment names used in app.py must have pricing entries."""
        from billing.model_pricing import MODEL_PRICING
        assert "gpt-5.2-chat" in MODEL_PRICING, "Primary chat model not priced"
        assert "gpt-5-mini" in MODEL_PRICING, "Classification model not priced"

    def test_tool_pricing_entries_have_required_keys(self):
        from billing.tool_pricing import TOOL_PRICING
        for name, entry in TOOL_PRICING.items():
            assert "cost_type" in entry, f"{name}: missing cost_type"
            assert "cost" in entry, f"{name}: missing cost"
            assert "description" in entry, f"{name}: missing description"
            assert isinstance(entry["cost"], Decimal), f"{name}: cost must be Decimal"
            assert entry["cost_type"] in ("flat", "variable"), (
                f"{name}: cost_type must be 'flat' or 'variable'"
            )

    def test_model_pricing_entries_have_required_keys(self):
        from billing.model_pricing import MODEL_PRICING
        for name, entry in MODEL_PRICING.items():
            assert "input_cost_per_1k" in entry, f"{name}: missing input_cost_per_1k"
            assert "output_cost_per_1k" in entry, f"{name}: missing output_cost_per_1k"
            assert isinstance(entry["input_cost_per_1k"], Decimal)
            assert isinstance(entry["output_cost_per_1k"], Decimal)
