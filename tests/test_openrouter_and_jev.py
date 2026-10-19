"""
Unit tests for OpenRouter client, cost tracking, budget enforcement, and Jev decision grounding
"""
import uuid
from decimal import Decimal
import pytest

from app.schemas.openrouter import JevDecisionResponse
from app.services.openrouter.client import (
    OpenRouterClient,
    OpenRouterBudgetExceededError,
    OpenRouterConfigError,
)
from app.services.openrouter.pricing import ModelPricingRegistry
from app.services.decision_engine.jev import JevDecisionEngine


def test_pricing_registry_calculation():
    # 1,000,000 prompt tokens + 1,000,000 completion tokens for claude-3.5-sonnet
    # $3.00 + $15.00 = $18.00
    cost = ModelPricingRegistry.calculate_estimated_cost(
        "anthropic/claude-3.5-sonnet", 1000000, 1000000
    )
    assert cost == Decimal("18.000000")

    # gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output
    cost_mini = ModelPricingRegistry.calculate_estimated_cost(
        "openai/gpt-4o-mini", 10000, 2000
    )
    # (10000/1M * 0.15) + (2000/1M * 0.60) = 0.0015 + 0.0012 = 0.002700
    assert cost_mini == Decimal("0.002700")


@pytest.mark.asyncio
async def test_budget_exceeded_raises():
    client = OpenRouterClient()
    with pytest.raises(OpenRouterBudgetExceededError, match="budget of"):
        await client.generate_chat_completion(
            messages=[{"role": "user", "content": "hello"}],
            model="openai/gpt-4o-mini",
            stage="extraction",
            accumulated_cost=Decimal("2.50"),  # Above limit $1.50
        )


@pytest.mark.asyncio
async def test_demo_mode_simulation(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    client = OpenRouterClient()
    result = await client.generate_chat_completion(
        messages=[{"role": "user", "content": "Extract transactions"}],
        model="anthropic/claude-3.5-sonnet",
        stage="extraction",
    )
    assert result.success is True
    assert result.is_simulated is True
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert result.parsed_json is not None
    assert "transactions" in result.parsed_json


def test_jev_grounding_rejects_hallucinated_ids():
    real_id_1 = str(uuid.uuid4())
    real_id_2 = str(uuid.uuid4())
    fake_id = str(uuid.uuid4())

    valid_ids = {real_id_1, real_id_2}
    valid_months = {"2026-03", "2026-04", "2026-05"}

    raw_decision = JevDecisionResponse(
        status="likely_salary",
        employer_candidate="Acme Corp",
        supporting_transaction_ids=[real_id_1, fake_id],
        supporting_months=["2026-03", "2026-99"],  # 2026-99 is invalid
        reason_codes=["RECURRING"],
        explanation="Consistent recurring salary found.",
        uncertainties=[],
        requires_human_review=False,
    )

    verified = JevDecisionEngine.verify_grounding(
        decision=raw_decision,
        valid_transaction_ids=valid_ids,
        valid_months=valid_months,
        financial_status="likely_salary",
    )

    # Hallucinated ID must be dropped
    assert fake_id not in verified.supporting_transaction_ids
    assert real_id_1 in verified.supporting_transaction_ids
    # Non-existent month must be dropped
    assert "2026-99" not in verified.supporting_months
    assert "2026-03" in verified.supporting_months
    # Human review must be forced due to hallucinated transaction ID
    assert verified.requires_human_review is True
    assert any("not present in source" in u for u in verified.uncertainties)
