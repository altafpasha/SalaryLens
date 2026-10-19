"""
Unit tests for database models and schema relationships
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    User,
    Organization,
    OrganizationMembership,
    Statement,
    Transaction,
    SalaryCandidateGroup,
    SalaryCandidate,
    AnalysisRun,
    ModelUsageEvent,
    HumanReview,
    AuditEvent,
    EmployerAlias,
    RetentionJob,
)


@pytest.mark.asyncio
async def test_full_model_lifecycle(db_session: AsyncSession):
    # 1. Organization
    org = Organization(
        name="Acme Finance Corp",
        slug="acme-finance",
    )
    db_session.add(org)
    await db_session.flush()
    assert org.id is not None

    # 2. User
    user = User(
        email="analyst@acmefinance.com",
        hashed_password="hashed_pw_example",
        full_name="Jane Doe",
        role="reviewer",
    )
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None

    # 3. Membership
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="reviewer",
    )
    db_session.add(membership)
    await db_session.flush()

    # 4. Statement
    stmt = Statement(
        organization_id=org.id,
        uploaded_by_user_id=user.id,
        filename="bank_statement_q2.pdf",
        file_path="/storage/uploads/mock_stmt.pdf",
        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=102400,
        page_count=3,
        duration_months=3,
        status="pending",
    )
    db_session.add(stmt)
    await db_session.flush()

    # 5. Transactions
    tx1 = Transaction(
        statement_id=stmt.id,
        organization_id=org.id,
        transaction_date=date(2026, 4, 30),
        raw_description="ACH CREDIT TECHCORP SALARY DIR DEP",
        normalized_description="TECHCORP SALARY DIR DEP",
        credit_amount=Decimal("4500.00"),
        page_number=1,
        is_salary_candidate=True,
        candidate_employer="TechCorp",
    )
    tx2 = Transaction(
        statement_id=stmt.id,
        organization_id=org.id,
        transaction_date=date(2026, 5, 29),
        raw_description="ACH CREDIT TECHCORP SALARY DIR DEP",
        normalized_description="TECHCORP SALARY DIR DEP",
        credit_amount=Decimal("4500.00"),
        page_number=2,
        is_salary_candidate=True,
        candidate_employer="TechCorp",
    )
    db_session.add_all([tx1, tx2])
    await db_session.flush()

    # 6. Candidate Group & Candidate
    group = SalaryCandidateGroup(
        statement_id=stmt.id,
        organization_id=org.id,
        employer_name="TechCorp",
        aliases=["TECHCORP SALARY DIR DEP"],
        transaction_count=2,
        months_count=2,
        average_amount=Decimal("4500.00"),
        median_amount=Decimal("4500.00"),
        min_amount=Decimal("4500.00"),
        max_amount=Decimal("4500.00"),
        amount_variation_pct=Decimal("0.00"),
        recurrence_score=Decimal("0.950"),
        is_primary=True,
    )
    db_session.add(group)
    await db_session.flush()

    cand1 = SalaryCandidate(
        group_id=group.id,
        transaction_id=tx1.id,
        organization_id=org.id,
        month_label="2026-04",
        day_of_month=30,
    )
    cand2 = SalaryCandidate(
        group_id=group.id,
        transaction_id=tx2.id,
        organization_id=org.id,
        month_label="2026-05",
        day_of_month=29,
    )
    db_session.add_all([cand1, cand2])
    await db_session.flush()

    # 7. Analysis Run
    run = AnalysisRun(
        statement_id=stmt.id,
        organization_id=org.id,
        status="completed",
        salary_status="likely_salary",
        detected_employer="TechCorp",
        supporting_transaction_ids=[str(tx1.id), str(tx2.id)],
        supporting_months=["2026-04", "2026-05"],
        reason_codes=["RECURRING_MONTHLY_CREDIT", "EXACT_AMOUNT_MATCH"],
        explanation="Consistent recurring salary credits detected from TechCorp.",
        requires_human_review=False,
        total_ai_cost_usd=Decimal("0.0042"),
        total_tokens=1500,
        is_demo=False,
    )
    db_session.add(run)
    await db_session.flush()

    # 8. Model Usage Event
    usage = ModelUsageEvent(
        statement_id=stmt.id,
        analysis_run_id=run.id,
        organization_id=org.id,
        model_name="anthropic/claude-3.5-sonnet",
        stage="extraction",
        input_tokens=1200,
        output_tokens=300,
        cached_tokens=0,
        estimated_cost_usd=Decimal("0.004200"),
        latency_ms=1150,
        retry_count=0,
        is_simulated=False,
        success=True,
    )
    db_session.add(usage)

    # 9. Human Review
    review = HumanReview(
        statement_id=stmt.id,
        organization_id=org.id,
        reviewer_user_id=user.id,
        status="approved",
        confirmed_employer="TechCorp",
        confirmed_transaction_ids=[str(tx1.id), str(tx2.id)],
        review_notes="Verified against employment contract.",
    )
    db_session.add(review)

    # 10. Audit Event
    audit = AuditEvent(
        organization_id=org.id,
        user_id=user.id,
        action="STATEMENT_APPROVED",
        resource_type="statement",
        resource_id=str(stmt.id),
        details_json={"notes": "All months verified"},
    )
    db_session.add(audit)

    # 11. Employer Alias
    alias = EmployerAlias(
        organization_id=org.id,
        canonical_name="TechCorp",
        alias="TECHCORP SALARY",
    )
    db_session.add(alias)

    # 12. Retention Job
    retention = RetentionJob(
        organization_id=org.id,
        status="completed",
        deleted_statements_count=0,
        deleted_files_count=0,
        executed_at=datetime.now(timezone.utc),
    )
    db_session.add(retention)

    await db_session.commit()

    # Verify query
    query_stmt = await db_session.execute(select(Statement).where(Statement.id == stmt.id))
    fetched_stmt = query_stmt.scalar_one()
    assert fetched_stmt.filename == "bank_statement_q2.pdf"
    assert len(fetched_stmt.transactions) == 2
    assert fetched_stmt.transactions[0].credit_amount == Decimal("4500.00")
