"""
SalaryLens AI by CodeSec — OpenRouter Model Pricing Registry
"""
from decimal import Decimal
from typing import Dict, Tuple

# Default pricing per million tokens (input_price_per_1m, output_price_per_1m)
DEFAULT_PRICING_REGISTRY: Dict[str, Tuple[Decimal, Decimal]] = {
    # Anthropic
    "anthropic/claude-3.5-sonnet": (Decimal("3.00"), Decimal("15.00")),
    "anthropic/claude-3-haiku": (Decimal("0.25"), Decimal("1.25")),
    # OpenAI
    "openai/gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "openai/gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "openai/gpt-4.1-mini": (Decimal("0.20"), Decimal("0.80")),
    # OpenRouter Configured Models
    "openai/gpt-6-luna": (Decimal("1.00"), Decimal("3.00")),
    "typesafe/jev-router": (Decimal("0.50"), Decimal("1.50")),
    "openai/text-embedding-3-large": (Decimal("0.13"), Decimal("0.00")),
    "openai/text-embedding-3-small": (Decimal("0.02"), Decimal("0.00")),
    # Embeddings
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0.00")),
    "text-embedding-3-large": (Decimal("0.13"), Decimal("0.00")),
    # Fallback
    "default": (Decimal("1.00"), Decimal("3.00")),
}


class ModelPricingRegistry:
    """Calculates estimated costs for AI requests when provider does not report exact cost."""

    @classmethod
    def calculate_estimated_cost(
        cls,
        model_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> Decimal:
        pricing = DEFAULT_PRICING_REGISTRY.get(model_name, DEFAULT_PRICING_REGISTRY["default"])
        input_rate_per_1m, output_rate_per_1m = pricing

        input_cost = (Decimal(str(input_tokens)) / Decimal("1000000")) * input_rate_per_1m
        output_cost = (Decimal(str(output_tokens)) / Decimal("1000000")) * output_rate_per_1m
        return (input_cost + output_cost).quantize(Decimal("0.000001"))
