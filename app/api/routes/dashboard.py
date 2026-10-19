"""
SalaryLens AI by CodeSec — Dashboard Aggregate Analytics Route
"""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_and_org, get_db_session
from app.models.statement import Statement
from app.models.analysis_run import AnalysisRun
from app.models.salary_candidate import SalaryCandidateGroup
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Dashboard Aggregate Metrics",
    description="Returns aggregate counts, status distributions, average salary, and spend for dashboard visualization."
)
async def get_dashboard_summary(
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardSummaryResponse:
    user, org_id, role = user_context

    # Total statements
    stmt_count_q = await db.execute(
        select(func.count(Statement.id)).where(Statement.organization_id == org_id)
    )
    total_statements = stmt_count_q.scalar() or 0

    # Analysis runs
    runs_q = await db.execute(
        select(AnalysisRun).where(AnalysisRun.organization_id == org_id)
    )
    runs = runs_q.scalars().all()

    likely_count = sum(1 for r in runs if r.salary_status == "likely_salary")
    possible_count = sum(1 for r in runs if r.salary_status == "possible_salary")
    multiple_count = sum(1 for r in runs if r.salary_status == "multiple_salary_candidates")
    insufficient_count = sum(1 for r in runs if r.salary_status == "insufficient_evidence")
    human_review_count = sum(1 for r in runs if r.requires_human_review)
    total_spend = sum(r.total_ai_cost_usd for r in runs) or Decimal("0.00")

    # Pending reviews (statements in requires_human_review)
    pending_reviews_q = await db.execute(
        select(func.count(Statement.id)).where(
            Statement.organization_id == org_id,
            Statement.status == "requires_human_review",
        )
    )
    pending_reviews = pending_reviews_q.scalar() or 0

    # Average monthly salary across primary candidate groups
    primary_groups_q = await db.execute(
        select(func.avg(SalaryCandidateGroup.average_amount)).where(
            SalaryCandidateGroup.organization_id == org_id,
            SalaryCandidateGroup.is_primary == True,
        )
    )
    avg_salary_val = primary_groups_q.scalar()
    avg_salary = Decimal(str(round(avg_salary_val, 2))) if avg_salary_val is not None else Decimal("0.00")

    return DashboardSummaryResponse(
        total_statements_processed=total_statements,
        likely_salary_count=likely_count,
        possible_salary_count=possible_count,
        multiple_candidates_count=multiple_count,
        insufficient_evidence_count=insufficient_count,
        requires_human_review_count=human_review_count,
        pending_reviews_count=pending_reviews,
        average_monthly_salary_usd=avg_salary,
        total_ai_spend_usd=total_spend.quantize(Decimal("0.0001")),
    )
