"""
SalaryLens AI by CodeSec — Admin Model Catalog & AI Usage Routes
"""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_and_org, get_db_session, require_role
from app.core.config import settings
from app.models.model_usage import ModelUsageEvent
from app.models.user import User
from app.schemas.admin import AdminModelsResponse, AdminUsageMetrics, ModelInfoItem
from app.services.openrouter.pricing import DEFAULT_PRICING_REGISTRY

router = APIRouter(prefix="/admin", tags=["Admin & AI Governance"])


@router.get(
    "/models",
    response_model=AdminModelsResponse,
    summary="Configured Model Catalog",
    description="Returns configured OpenRouter model identifiers and pricing metadata without exposing secrets."
)
async def get_admin_models(
    user_context: tuple[User, uuid.UUID, str] = Depends(require_role("reviewer")),
) -> AdminModelsResponse:
    # Model catalog
    finder_pricing = DEFAULT_PRICING_REGISTRY.get(settings.SALARY_FINDER_MODEL, (Decimal("3.00"), Decimal("15.00")))
    decision_pricing = DEFAULT_PRICING_REGISTRY.get(settings.DECISION_MODEL, (Decimal("0.15"), Decimal("0.60")))
    embed_pricing = DEFAULT_PRICING_REGISTRY.get(settings.EMBEDDING_MODEL, (Decimal("0.02"), Decimal("0.00")))

    items = [
        ModelInfoItem(
            model_id=settings.SALARY_FINDER_MODEL,
            role="salary_finder",
            input_price_per_1m=finder_pricing[0],
            output_price_per_1m=finder_pricing[1],
            supports_vision=True if "claude" in settings.SALARY_FINDER_MODEL or "gpt-4" in settings.SALARY_FINDER_MODEL else False,
        ),
        ModelInfoItem(
            model_id=settings.DECISION_MODEL,
            role="decision_engine",
            input_price_per_1m=decision_pricing[0],
            output_price_per_1m=decision_pricing[1],
            supports_vision=False,
        ),
        ModelInfoItem(
            model_id=settings.EMBEDDING_MODEL,
            role="embedding",
            input_price_per_1m=embed_pricing[0],
            output_price_per_1m=embed_pricing[1],
            supports_vision=False,
        ),
    ]

    return AdminModelsResponse(
        models=items,
        max_budget_per_statement_usd=Decimal(str(settings.MAX_AI_COST_USD_PER_STATEMENT)),
        demo_mode_enabled=settings.DEMO_MODE,
    )


@router.get(
    "/usage",
    response_model=AdminUsageMetrics,
    summary="Authorized AI Usage & Cost Analytics",
    description="Returns aggregated token usage, cost breakdowns, and latency metrics for the tenant."
)
async def get_admin_usage(
    user_context: tuple[User, uuid.UUID, str] = Depends(require_role("reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUsageMetrics:
    user, org_id, role = user_context

    # Query all model usage events for the tenant
    events_q = await db.execute(
        select(ModelUsageEvent).where(ModelUsageEvent.organization_id == org_id)
    )
    events = events_q.scalars().all()

    total_calls = len(events)
    total_tokens = sum(e.input_tokens + e.output_tokens for e in events)
    total_cost = sum(
        (e.provider_cost_usd if e.provider_cost_usd is not None else e.estimated_cost_usd)
        for e in events
    ) or Decimal("0.000000")
    total_simulated = sum(1 for e in events if e.is_simulated)
    avg_latency = (sum(e.latency_ms for e in events) / total_calls) if total_calls > 0 else 0.0

    stage_breakdown = {}
    model_breakdown = {}
    for e in events:
        stage_breakdown[e.stage] = stage_breakdown.get(e.stage, 0) + 1
        model_breakdown[e.model_name] = model_breakdown.get(e.model_name, 0) + 1

    return AdminUsageMetrics(
        total_model_calls=total_calls,
        total_tokens_consumed=total_tokens,
        total_cost_usd=total_cost.quantize(Decimal("0.0001")),
        total_simulated_calls=total_simulated,
        average_latency_ms=round(avg_latency, 2),
        usage_by_stage=stage_breakdown,
        usage_by_model=model_breakdown,
    )
