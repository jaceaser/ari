"""
LLM model pricing configuration and cost calculator.

Prices are USD per 1,000 tokens. All values use Decimal to avoid
floating-point errors in billing arithmetic.

Sources: Azure OpenAI pricing (verify and update when pricing changes).
GPT-5.x prices are estimates — update once Azure publishes official rates.

Key principle: unknown models return Decimal("0") with a logged warning
so a missing entry never crashes a user request.
"""
import logging
from decimal import Decimal
from typing import TypedDict

logger = logging.getLogger("ari.billing.model_pricing")


class ModelPricing(TypedDict):
    input_cost_per_1k: Decimal   # USD per 1,000 input (prompt) tokens
    output_cost_per_1k: Decimal  # USD per 1,000 output (completion) tokens


# Registry keyed by Azure OpenAI deployment name (value of AZURE_OPENAI_DEPLOYMENT
# / AZURE_OPENAI_CLASSIFICATION_MODEL env vars).
MODEL_PRICING: dict[str, ModelPricing] = {
    # Primary chat model — app.py AZURE_OPENAI_DEPLOYMENT default
    "gpt-5.2-chat": ModelPricing(
        input_cost_per_1k=Decimal("0.005000"),   # $5.00 / 1M tokens
        output_cost_per_1k=Decimal("0.015000"),  # $15.00 / 1M tokens
    ),
    # Classification model — app.py AZURE_OPENAI_CLASSIFICATION_MODEL default
    "gpt-5-mini": ModelPricing(
        input_cost_per_1k=Decimal("0.000150"),   # $0.15 / 1M tokens
        output_cost_per_1k=Decimal("0.000600"),  # $0.60 / 1M tokens
    ),
    # Common fallback aliases in case deployment names differ across envs
    "gpt-4o": ModelPricing(
        input_cost_per_1k=Decimal("0.002500"),
        output_cost_per_1k=Decimal("0.010000"),
    ),
    "gpt-4o-mini": ModelPricing(
        input_cost_per_1k=Decimal("0.000150"),
        output_cost_per_1k=Decimal("0.000600"),
    ),
}


def calculate_token_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """
    Return the estimated USD cost for one LLM call.

    Returns Decimal("0") for unknown models and logs a warning so pricing
    gaps are visible in logs without crashing anything.

    Uses Decimal arithmetic throughout — never float — to avoid precision
    loss when these values are summed across many events.
    """
    pricing = MODEL_PRICING.get(model_name)
    if pricing is None:
        logger.warning(
            "Unknown model '%s' — no pricing data, cost recorded as $0.00. "
            "Add this model to billing/model_pricing.py.",
            model_name,
        )
        return Decimal("0")

    input_cost = pricing["input_cost_per_1k"] * Decimal(input_tokens) / Decimal(1000)
    output_cost = pricing["output_cost_per_1k"] * Decimal(output_tokens) / Decimal(1000)
    return (input_cost + output_cost).quantize(Decimal("0.000001"))
