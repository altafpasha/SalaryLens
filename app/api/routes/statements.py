"""
SalaryLens AI by CodeSec — Statement Lifecycle and Review Routes
"""
import os
import re
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_and_org, get_db_session, require_role
from app.core.config import settings
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.salary_candidate import SalaryCandidateGroup
from app.models.analysis_run import AnalysisRun
from app.models.model_usage import ModelUsageEvent
from app.models.human_review import HumanReview
from app.models.audit import AuditEvent
from app.models.user import User
from app.services.reporting.workbook import ExcelWorkbookGenerator
from app.schemas.statement import (
    CandidateGroupSummary,
    HumanReviewRequest,
    HumanReviewResponse,
    PaginatedTransactionsResponse,
    StatementListItem,
    StatementResultsResponse,
    StatementStatusResponse,
    StatementTransactionItem,
    StatementUploadResponse,
)
from app.services.document_processing.validator import DocumentValidator, DocumentValidationError
from app.services.document_processing.storage import StorageService
from app.workers.tasks import run_statement_processing_pipeline

router = APIRouter(prefix="/statements", tags=["Statements"])


@router.post(
    "",
    response_model=StatementUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Bank Statement PDF",
    description="Uploads a bank statement PDF (3 or 6 months), validates signature/pages, stores privately, and enqueues asynchronous analysis."
)
async def upload_statement(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Bank statement PDF file"),
    duration_months: Optional[int] = Form(None, description="Optional expected duration in months (3 or 6)"),
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> StatementUploadResponse:
    user, org_id, role = user_context

    if duration_months is not None and duration_months not in [3, 6]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="duration_months must be either 3 or 6 if provided.",
        )

    # 1. Validate PDF signature, corruption, size, page count
    try:
        file_hash, file_size, page_count = DocumentValidator.validate_pdf_stream(
            file.file, file.filename or "statement.pdf"
        )
    except DocumentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 2. Save document to private storage
    statement_id = uuid.uuid4()
    saved_path = StorageService.save_upload_stream(
        organization_id=org_id,
        statement_id=statement_id,
        file_stream=file.file,
        file_hash=file_hash,
    )

    # 3. Create Statement record
    statement = Statement(
        id=statement_id,
        organization_id=org_id,
        uploaded_by_user_id=user.id,
        filename=file.filename or "statement.pdf",
        file_path=saved_path,
        file_hash=file_hash,
        file_size_bytes=file_size,
        page_count=page_count,
        duration_months=duration_months,
        status="pending",
        is_demo=settings.DEMO_MODE,
    )
    db.add(statement)

    # Audit log
    audit = AuditEvent(
        organization_id=org_id,
        user_id=user.id,
        action="STATEMENT_UPLOADED",
        resource_type="statement",
        resource_id=str(statement.id),
        details_json={"filename": file.filename, "size_bytes": file_size, "page_count": page_count},
    )
    db.add(audit)
    await db.commit()

    # 4. Enqueue background processing
    background_tasks.add_task(
        run_statement_processing_pipeline,
        str(statement.id),
        str(org_id),
    )

    return StatementUploadResponse(
        statement_id=statement.id,
        filename=statement.filename,
        file_size_bytes=statement.file_size_bytes,
        page_count=statement.page_count,
        duration_months=statement.duration_months,
        status=statement.status,
        is_demo=statement.is_demo,
        created_at=statement.created_at,
    )


@router.get(
    "",
    response_model=list[StatementListItem],
    summary="List Bank Statements",
    description="Lists all uploaded bank statements for the user's organization.",
)
async def list_statements(
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> list[StatementListItem]:
    user, org_id, role = user_context
    result = await db.execute(
        select(Statement)
        .where(Statement.organization_id == org_id)
        .order_by(desc(Statement.created_at))
    )
    statements = result.scalars().all()

    stmt_ids = [s.id for s in statements]
    runs_by_stmt = {}
    groups_by_stmt = {}
    if stmt_ids:
        runs_q = await db.execute(
            select(AnalysisRun).where(
                AnalysisRun.statement_id.in_(stmt_ids),
                AnalysisRun.organization_id == org_id,
            ).order_by(desc(AnalysisRun.created_at))
        )
        for r in runs_q.scalars().all():
            if r.statement_id not in runs_by_stmt:
                runs_by_stmt[r.statement_id] = r

        groups_q = await db.execute(
            select(SalaryCandidateGroup).where(
                SalaryCandidateGroup.statement_id.in_(stmt_ids),
                SalaryCandidateGroup.organization_id == org_id,
            )
        )
        all_candidate_groups = groups_q.scalars().all()
        for g in all_candidate_groups:
            if g.is_primary or g.statement_id not in groups_by_stmt:
                groups_by_stmt[g.statement_id] = g

    items = []
    for s in statements:
        run = runs_by_stmt.get(s.id)
        grp = groups_by_stmt.get(s.id)
        avg_amt = None
        if run and run.detected_employer:
            for g in all_candidate_groups:
                if g.statement_id == s.id and g.employer_name.upper() == run.detected_employer.upper():
                    avg_amt = g.average_amount
                    break
        if avg_amt is None and grp:
            avg_amt = grp.average_amount

        items.append(
            StatementListItem(
                statement_id=s.id,
                filename=s.filename,
                file_size_bytes=s.file_size_bytes,
                page_count=s.page_count,
                duration_months=s.duration_months,
                status=s.status,
                is_scanned=s.is_scanned,
                workbook_status=s.workbook_status,
                total_transactions_count=s.total_transactions_count or 0,
                included_in_salary_count=s.included_in_salary_count or 0,
                excluded_from_salary_count=s.excluded_from_salary_count or 0,
                detected_employer=run.detected_employer if (run and run.detected_employer) else (grp.employer_name if grp else None),
                salary_status=run.salary_status if run else None,
                average_salary=avg_amt,
                currency="INR",
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return items


@router.get(
    "/{statement_id}/status",
    response_model=StatementStatusResponse,
    summary="Check Statement Processing Status",
    description="Returns processing status (pending, processing, completed, requires_human_review, failed)."
)
async def get_statement_status(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> StatementStatusResponse:
    user, org_id, role = user_context

    result = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = result.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    return StatementStatusResponse(
        statement_id=statement.id,
        status=statement.status,
        is_scanned=statement.is_scanned,
        page_count=statement.page_count,
        error_message=statement.error_message,
        workbook_status=statement.workbook_status,
        workbook_generated_at=statement.workbook_generated_at,
        total_transactions_count=statement.total_transactions_count,
        included_in_salary_count=statement.included_in_salary_count,
        excluded_from_salary_count=statement.excluded_from_salary_count,
        created_at=statement.created_at,
        updated_at=statement.updated_at,
    )


@router.get(
    "/{statement_id}/results",
    response_model=StatementResultsResponse,
    summary="Get Validated Salary Analysis Results",
    description="Returns the validated salary finding, supporting transaction IDs, candidate groups, and AI costs."
)
async def get_statement_results(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> StatementResultsResponse:
    user, org_id, role = user_context

    # Verify statement ownership
    stmt_q = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_q.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    # Fetch latest analysis run
    run_q = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.statement_id == statement_id,
            AnalysisRun.organization_id == org_id,
        ).order_by(desc(AnalysisRun.created_at))
    )
    analysis_run = run_q.scalar_one_or_none()
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis results not yet available. Processing may still be in progress.",
        )

    # Fetch candidate groups
    group_q = await db.execute(
        select(SalaryCandidateGroup).where(
            SalaryCandidateGroup.statement_id == statement_id,
            SalaryCandidateGroup.organization_id == org_id,
        )
    )
    groups = group_q.scalars().all()
    group_summaries = [
        CandidateGroupSummary(
            employer_name=g.employer_name,
            aliases=g.aliases or [],
            transaction_count=g.transaction_count,
            months_count=g.months_count,
            missing_months=g.missing_months or [],
            average_amount=g.average_amount,
            median_amount=g.median_amount,
            min_amount=g.min_amount,
            max_amount=g.max_amount,
            amount_variation_pct=g.amount_variation_pct,
            recurrence_score=g.recurrence_score,
            is_primary=g.is_primary,
        )
        for g in groups
    ]

    # Ensure a primary candidate group is designated
    has_primary = any(g.is_primary for g in group_summaries)
    if not has_primary and group_summaries:
        matched = False
        if analysis_run.detected_employer:
            for gs in group_summaries:
                if gs.employer_name.upper() == analysis_run.detected_employer.upper():
                    gs.is_primary = True
                    matched = True
                    break
        if not matched and group_summaries:
            group_summaries[0].is_primary = True

    # Identify primary candidate group
    primary_group = next((g for g in groups if g.is_primary), None)
    if not primary_group and groups:
        if analysis_run.detected_employer:
            primary_group = next((g for g in groups if g.employer_name.upper() == analysis_run.detected_employer.upper()), groups[0])
        else:
            primary_group = groups[0]

    estimated_monthly_salary = primary_group.average_amount if primary_group else None
    salary_transaction_count = len(analysis_run.supporting_transaction_ids or [])
    if not salary_transaction_count and primary_group:
        salary_transaction_count = primary_group.transaction_count

    months_analyzed_count = len(analysis_run.supporting_months or [])
    if not months_analyzed_count and primary_group:
        months_analyzed_count = primary_group.months_count

    # Determine confidence score (0 - 100)
    confidence_score = 50
    if primary_group and primary_group.recurrence_score:
        confidence_score = int(round(float(primary_group.recurrence_score) * 100))
    if analysis_run.salary_status == "likely_salary":
        confidence_score = max(confidence_score, 88)
    elif analysis_run.salary_status == "possible_salary":
        confidence_score = min(max(confidence_score, 65), 84)
    elif analysis_run.salary_status == "multiple_salary_candidates":
        confidence_score = min(max(confidence_score, 55), 75)
    elif analysis_run.salary_status in ("insufficient_evidence", "conflicting_evidence", "analysis_failed"):
        confidence_score = min(confidence_score, 35)

    # Fetch model diagnostics
    diag_q = await db.execute(
        select(ModelUsageEvent).where(
            ModelUsageEvent.analysis_run_id == analysis_run.id
        ).order_by(ModelUsageEvent.created_at.asc())
    )
    usage_events = diag_q.scalars().all()
    model_diagnostics = [
        {
            "stage": ev.stage,
            "model_name": ev.model_name,
            "input_tokens": ev.input_tokens,
            "output_tokens": ev.output_tokens,
            "total_tokens": ev.input_tokens + ev.output_tokens,
            "latency_ms": ev.latency_ms,
            "provider_cost_usd": float(ev.provider_cost_usd or ev.estimated_cost_usd),
            "is_simulated": ev.is_simulated,
            "success": ev.success,
        }
        for ev in usage_events
    ]

    # Structure Jev Decision Engine details
    jev_decision = {
        "status": analysis_run.salary_status,
        "recommended_employer": analysis_run.detected_employer,
        "estimated_monthly_salary": float(estimated_monthly_salary) if estimated_monthly_salary is not None else None,
        "confidence_score": confidence_score,
        "reasoning": analysis_run.explanation,
        "supporting_transaction_ids": analysis_run.supporting_transaction_ids or [],
        "supporting_months": analysis_run.supporting_months or [],
        "reason_codes": analysis_run.reason_codes or [],
        "uncertainties": analysis_run.uncertainties or [],
        "requires_human_review": analysis_run.requires_human_review,
        "model_name": usage_events[-1].model_name if usage_events else settings.DECISION_MODEL,
        "prompt_version": "v2.0-financial-rag",
    }

    return StatementResultsResponse(
        statement_id=statement.id,
        status=analysis_run.salary_status,
        detected_employer=analysis_run.detected_employer,
        supporting_transaction_ids=analysis_run.supporting_transaction_ids or [],
        supporting_months=analysis_run.supporting_months or [],
        reason_codes=analysis_run.reason_codes or [],
        explanation=analysis_run.explanation,
        uncertainties=analysis_run.uncertainties or [],
        requires_human_review=analysis_run.requires_human_review,
        candidate_groups=group_summaries,
        total_ai_cost_usd=analysis_run.total_ai_cost_usd,
        total_tokens=analysis_run.total_tokens,
        is_demo=analysis_run.is_demo,
        currency="INR",
        confidence_score=confidence_score,
        estimated_monthly_salary=estimated_monthly_salary,
        salary_transaction_count=salary_transaction_count,
        months_analyzed_count=months_analyzed_count,
        jev_decision=jev_decision,
        model_diagnostics=model_diagnostics,
        analysis_completed_at=analysis_run.completed_at,
    )


@router.get(
    "/{statement_id}/transactions",
    response_model=PaginatedTransactionsResponse,
    summary="Get Paginated Statement Transactions",
    description="Returns extracted transactions with pagination."
)
async def get_statement_transactions(
    statement_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    included_only: Optional[bool] = Query(None, description="Filter for salary-analysis dataset only"),
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedTransactionsResponse:
    user, org_id, role = user_context

    # Verify statement
    stmt_q = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    if not stmt_q.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    # Base query
    base_conditions = [
        Transaction.statement_id == statement_id,
        Transaction.organization_id == org_id,
    ]
    if included_only is not None:
        base_conditions.append(Transaction.included_in_salary_analysis == included_only)

    # Count total
    count_q = await db.execute(
        select(func.count(Transaction.id)).where(*base_conditions)
    )
    total_count = count_q.scalar() or 0

    # Fetch page
    tx_q = await db.execute(
        select(Transaction)
        .where(*base_conditions)
        .order_by(Transaction.transaction_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = tx_q.scalars().all()

    tx_items = [
        StatementTransactionItem(
            id=t.id,
            transaction_date=t.transaction_date,
            value_date=t.value_date,
            raw_description=t.raw_description,
            normalized_description=t.normalized_description,
            credit_amount=t.credit_amount,
            debit_amount=t.debit_amount,
            balance=t.balance,
            currency=t.currency,
            page_number=t.page_number,
            transaction_direction=t.transaction_direction,
            category=t.category,
            included_in_salary_analysis=t.included_in_salary_analysis,
            exclusion_reason=t.exclusion_reason,
            inclusion_reason=t.inclusion_reason,
            validation_status=t.validation_status,
            is_salary_candidate=t.is_salary_candidate,
            candidate_employer=t.candidate_employer,
            is_reversal=t.is_reversal,
            is_duplicate=t.is_duplicate,
        )
        for t in items
    ]

    return PaginatedTransactionsResponse(
        statement_id=statement_id,
        total_count=total_count,
        page=page,
        page_size=page_size,
        transactions=tx_items,
    )


@router.post(
    "/{statement_id}/analyze",
    response_model=StatementStatusResponse,
    summary="Trigger or Restart Statement Analysis",
    description="Restarts or retries analysis pipeline safely, preventing duplicate processing."
)
async def analyze_statement(
    statement_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> StatementStatusResponse:
    user, org_id, role = user_context

    stmt_q = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_q.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    if statement.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Statement analysis is already actively processing.",
        )

    statement.status = "pending"
    statement.error_message = None
    await db.commit()

    background_tasks.add_task(
        run_statement_processing_pipeline,
        str(statement.id),
        str(org_id),
    )

    return StatementStatusResponse(
        statement_id=statement.id,
        status=statement.status,
        is_scanned=statement.is_scanned,
        page_count=statement.page_count,
        error_message=statement.error_message,
        created_at=statement.created_at,
        updated_at=statement.updated_at,
    )


@router.post(
    "/{statement_id}/review",
    response_model=HumanReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Human Review Decision",
    description="Records a human reviewer override or confirmation. Requires reviewer or admin role."
)
async def review_statement(
    statement_id: uuid.UUID,
    review_data: HumanReviewRequest,
    user_context: tuple[User, uuid.UUID, str] = Depends(require_role("reviewer")),
    db: AsyncSession = Depends(get_db_session),
) -> HumanReviewResponse:
    user, org_id, role = user_context

    stmt_q = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_q.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    review = HumanReview(
        statement_id=statement.id,
        organization_id=org_id,
        reviewer_user_id=user.id,
        status=review_data.status,
        confirmed_employer=review_data.confirmed_employer,
        confirmed_transaction_ids=review_data.confirmed_transaction_ids,
        review_notes=review_data.review_notes,
    )
    db.add(review)

    # Update statement status based on review
    if review_data.status in ["approved", "adjusted"]:
        statement.status = "completed"
    elif review_data.status == "rejected":
        statement.status = "failed"
        statement.error_message = f"Rejected in human review: {review_data.review_notes or 'No notes provided'}"

    # Audit log
    audit = AuditEvent(
        organization_id=org_id,
        user_id=user.id,
        action="STATEMENT_REVIEW_SUBMITTED",
        resource_type="human_review",
        resource_id=str(review.id),
        details_json={
            "statement_id": str(statement.id),
            "review_status": review_data.status,
            "confirmed_employer": review_data.confirmed_employer,
        },
    )
    db.add(audit)

    # Update workbook if present to reflect reviewer decision
    if statement.workbook_file_path and os.path.exists(statement.workbook_file_path):
        try:
            from app.services.reporting.workbook import ExcelWorkbookGenerator
            cg_q = await db.execute(select(SalaryCandidateGroup).where(SalaryCandidateGroup.statement_id == statement_id))
            c_groups = cg_q.scalars().all()
            tx_q = await db.execute(select(Transaction).where(Transaction.statement_id == statement_id))
            all_txs = tx_q.scalars().all()
            tx_dicts = [{
                "id": t.id,
                "transaction_date": t.transaction_date,
                "value_date": t.value_date,
                "raw_description": t.raw_description,
                "credit_amount": t.credit_amount,
                "debit_amount": t.debit_amount,
                "balance": t.balance,
                "currency": t.currency,
                "confidence": t.confidence,
                "included_in_salary_analysis": t.included_in_salary_analysis,
            } for t in all_txs]

            run_q = await db.execute(select(AnalysisRun).where(AnalysisRun.statement_id == statement_id).order_by(desc(AnalysisRun.created_at)))
            a_run = run_q.scalar_one_or_none()

            ExcelWorkbookGenerator.finalize_workbook(
                workbook_path=Path(statement.workbook_file_path),
                statement=statement,
                candidate_groups=c_groups,
                analysis_run=a_run,
                transactions=tx_dicts,
                filtering_stats={
                    "total_transactions": statement.total_transactions_count,
                    "total_debits": statement.total_debit_count,
                    "total_credits": statement.total_credit_count,
                    "included_in_salary_analysis": statement.included_in_salary_count,
                    "excluded_from_salary_analysis": statement.excluded_from_salary_count,
                },
                reviewer_decision={
                    "status": review_data.status,
                    "confirmed_employer": review_data.confirmed_employer,
                    "review_notes": review_data.review_notes,
                }
            )
        except Exception:
            pass

    await db.commit()

    return HumanReviewResponse(
        review_id=review.id,
        statement_id=statement.id,
        reviewer_user_id=user.id,
        status=review.status,
        confirmed_employer=review.confirmed_employer,
        confirmed_transaction_ids=review.confirmed_transaction_ids or [],
        review_notes=review.review_notes,
        created_at=review.created_at,
    )


@router.get(
    "/{statement_id}/download",
    summary="Secure Excel Workbook Download",
    description="Downloads the 5-sheet financial Excel workbook. Available to organization tenant members."
)
async def download_statement_workbook(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
):
    user, org_id, role = user_context

    # 1. Tenant-scoped query
    stmt_q = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_q.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    # 2. Check if workbook generation is in progress or completed
    if statement.status == "processing" and not statement.workbook_file_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workbook generation is currently in progress. Please poll status until complete."
        )

    # 3. Generate fresh, standardized 5-sheet workbook in INR
    wb_dir = Path(settings.STORAGE_ROOT) / "workbooks" / str(org_id) / str(statement.id)
    wb_dir.mkdir(parents=True, exist_ok=True)
    wb_path = wb_dir / f"statement_{statement.id}_analysis.xlsx"

    tx_q = await db.execute(
        select(Transaction).where(Transaction.statement_id == statement.id).order_by(Transaction.transaction_date.asc())
    )
    txs = tx_q.scalars().all()
    tx_dicts = [{
        "id": str(t.id),
        "transaction_date": t.transaction_date,
        "value_date": t.value_date,
        "raw_description": t.raw_description,
        "description": t.raw_description,
        "credit_amount": t.credit_amount,
        "debit_amount": t.debit_amount,
        "balance": t.balance,
        "currency": "INR" if (not t.currency or t.currency.upper() in ("USD", "NULL", "NONE")) else t.currency,
        "page_number": t.page_number,
        "confidence": t.confidence,
        "included_in_salary_analysis": t.included_in_salary_analysis,
        "exclusion_reason": t.exclusion_reason,
        "inclusion_reason": t.inclusion_reason,
        "candidate_employer": t.candidate_employer,
    } for t in txs]

    group_q = await db.execute(select(SalaryCandidateGroup).where(SalaryCandidateGroup.statement_id == statement.id))
    c_groups = group_q.scalars().all()

    run_q = await db.execute(
        select(AnalysisRun).where(AnalysisRun.statement_id == statement.id).order_by(desc(AnalysisRun.created_at))
    )
    a_run = run_q.scalar_one_or_none()

    filtering_stats = {
        "total_transactions": statement.total_transactions_count or len(txs),
        "total_debits": statement.total_debit_count or sum(1 for t in txs if t.debit_amount),
        "total_credits": statement.total_credit_count or sum(1 for t in txs if t.credit_amount),
        "included_in_salary_analysis": statement.included_in_salary_count or sum(1 for t in txs if t.included_in_salary_analysis),
        "excluded_from_salary_analysis": statement.excluded_from_salary_count or sum(1 for t in txs if not t.included_in_salary_analysis),
    }

    # Check for reviewer decision
    rev_q = await db.execute(
        select(HumanReview).where(HumanReview.statement_id == statement.id).order_by(desc(HumanReview.created_at))
    )
    latest_rev = rev_q.scalar_one_or_none()
    rev_decision = None
    if latest_rev:
        rev_decision = {
            "status": latest_rev.status,
            "confirmed_employer": latest_rev.confirmed_employer,
            "review_notes": latest_rev.review_notes,
        }

    acct_dict = dict(statement.account_info_json or {})
    acct_dict.setdefault("bank_data_customer_account_info_id", str(statement.id))
    acct_dict.setdefault("name", "Account Holder")
    acct_dict.setdefault("start_date", str(statement.statement_start_date or ""))
    acct_dict.setdefault("end_date", str(statement.statement_end_date or ""))

    ExcelWorkbookGenerator.generate_initial_workbook(
        statement=statement,
        account_info=acct_dict,
        transactions=tx_dicts,
        filtering_stats=filtering_stats,
        output_path=wb_path,
    )

    if a_run or c_groups:
        ExcelWorkbookGenerator.finalize_workbook(
            workbook_path=wb_path,
            statement=statement,
            candidate_groups=c_groups,
            analysis_run=a_run,
            transactions=tx_dicts,
            filtering_stats=filtering_stats,
            ai_cost=a_run.total_ai_cost_usd if a_run else Decimal("0.00"),
            ai_tokens=a_run.total_tokens if a_run else 0,
            reviewer_decision=rev_decision,
        )

    statement.workbook_file_path = str(wb_path)
    statement.workbook_status = "completed"
    statement.workbook_validation_status = "verified"
    await db.commit()

    # 4. Log download audit event
    audit = AuditEvent(
        organization_id=org_id,
        user_id=user.id,
        action="STATEMENT_WORKBOOK_DOWNLOADED",
        resource_type="workbook",
        resource_id=str(statement.id),
        details_json={
            "statement_id": str(statement.id),
            "filename": statement.filename,
            "workbook_status": statement.workbook_status,
        },
    )
    db.add(audit)
    await db.commit()

    # 4. Safe filename
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', statement.filename.rsplit('.', 1)[0])
    download_name = f"SalaryLens_{clean_name}_Analysis.xlsx"

    return FileResponse(
        path=statement.workbook_file_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.delete(
    "/{statement_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Statement (CRUD Delete)",
    description="Deletes a bank statement, all extracted transactions, candidate groups, analysis runs, and associated files."
)
async def delete_statement(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
):
    user, org_id, role = user_context

    stmt_res = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_res.scalar_one_or_none()
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found or does not belong to your organization."
        )

    # 1. Clean up physical files
    if statement.file_path and os.path.exists(statement.file_path):
        try:
            os.remove(statement.file_path)
        except Exception:
            pass

    wb_dir = Path(settings.STORAGE_ROOT) / "workbooks" / str(org_id) / str(statement.id)
    if wb_dir.exists():
        shutil.rmtree(wb_dir, ignore_errors=True)

    render_dir = Path(settings.STORAGE_ROOT) / "renders" / str(org_id) / str(statement.id)
    if render_dir.exists():
        shutil.rmtree(render_dir, ignore_errors=True)

    # 2. Log audit event
    audit = AuditEvent(
        organization_id=org_id,
        user_id=user.id,
        action="STATEMENT_DELETED",
        resource_type="statement",
        resource_id=str(statement.id),
        details_json={
            "statement_id": str(statement.id),
            "filename": statement.filename,
            "deleted_by": user.email,
        },
    )
    db.add(audit)

    # 3. Delete from DB (cascades to transactions, candidates, runs, reviews)
    await db.delete(statement)
    await db.commit()

    return {
        "success": True,
        "message": f"Statement '{statement.filename}' and all associated transactions deleted successfully.",
        "statement_id": str(statement.id),
    }


@router.get(
    "/{statement_id}/logs",
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Execution Logs & Explanation (How It Works)",
    description="Returns chronological pipeline logs, stage transitions, and AI model telemetry explaining how analysis works."
)
async def get_statement_logs(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
):
    user, org_id, role = user_context

    stmt_res = await db.execute(
        select(Statement).where(
            Statement.id == statement_id,
            Statement.organization_id == org_id,
        )
    )
    statement = stmt_res.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")

    audit_res = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.resource_id == str(statement.id))
        .order_by(AuditEvent.created_at.asc())
    )
    audits = audit_res.scalars().all()

    usage_res = await db.execute(
        select(ModelUsageEvent)
        .where(ModelUsageEvent.statement_id == statement.id)
        .order_by(ModelUsageEvent.created_at.asc())
    )
    usages = usage_res.scalars().all()

    run_res = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.statement_id == statement.id)
        .order_by(desc(AnalysisRun.created_at))
    )
    latest_run = run_res.scalar_one_or_none()

    logs = []

    # 1. Ingestion
    logs.append({
        "timestamp": statement.created_at.isoformat() if statement.created_at else "",
        "stage": "INGESTION",
        "level": "SUCCESS",
        "title": "Document Uploaded & Verified",
        "message": f"Uploaded '{statement.filename}' ({statement.page_count} pages, {statement.file_size_bytes} bytes). SHA-256 integrity hash verified.",
        "metadata": {
            "page_count": statement.page_count,
            "is_scanned": statement.is_scanned,
            "sha256": statement.file_hash,
        }
    })

    # 2. Text & Layout Extraction
    if statement.total_transactions_count > 0 or statement.status in ["completed", "requires_human_review", "failed"]:
        extract_level = "SUCCESS" if statement.total_transactions_count > 0 else "WARNING"
        logs.append({
            "timestamp": statement.updated_at.isoformat() if statement.updated_at else "",
            "stage": "EXTRACTION",
            "level": extract_level,
            "title": "Document Parsing & Layout Analysis",
            "message": f"Processed {statement.page_count} pages ({statement.native_pages_count} native, {statement.ocr_pages_count} OCR fallback). Extracted {statement.total_transactions_count} total ledger transactions.",
            "metadata": {
                "total_transactions": statement.total_transactions_count,
                "native_pages": statement.native_pages_count,
                "ocr_pages": statement.ocr_pages_count,
            }
        })

    # 3. Deterministic Financial Filtering
    if statement.total_transactions_count > 0:
        logs.append({
            "timestamp": statement.updated_at.isoformat() if statement.updated_at else "",
            "stage": "FILTERING",
            "level": "INFO",
            "title": "Deterministic Financial Safeguards",
            "message": f"Categorized {statement.total_debit_count} debits and {statement.total_credit_count} credits. Retained {statement.included_in_salary_count} potential salary entries; filtered out {statement.excluded_from_salary_count} non-payroll transactions (P2P UPI, refunds, fees).",
            "metadata": {
                "total_debits": statement.total_debit_count,
                "total_credits": statement.total_credit_count,
                "included_in_salary": statement.included_in_salary_count,
                "excluded_from_salary": statement.excluded_from_salary_count,
            }
        })

    # 4. AI Model Usage Events (OpenRouter telemetry)
    for u in usages:
        cost_inr = float(u.provider_cost_usd or u.estimated_cost_usd or 0) * 86.0
        logs.append({
            "timestamp": u.created_at.isoformat() if u.created_at else "",
            "stage": f"AI_{u.stage.upper()}",
            "level": "SUCCESS" if u.success else "ERROR",
            "title": f"OpenRouter Call — {u.stage.capitalize()}",
            "message": f"Executed model '{u.model_name}' ({u.input_tokens} in / {u.output_tokens} out tokens) in {u.latency_ms}ms. Estimated cost: ₹{cost_inr:.2f}.",
            "metadata": {
                "model": u.model_name,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cached_tokens": u.cached_tokens,
                "latency_ms": u.latency_ms,
                "cost_inr": round(cost_inr, 2),
            }
        })

    # 5. Jev Decision Engine
    if latest_run:
        logs.append({
            "timestamp": latest_run.created_at.isoformat() if latest_run.created_at else "",
            "stage": "DECISION_ENGINE",
            "level": "SUCCESS" if latest_run.salary_status in ["likely_salary", "possible_salary"] else "WARNING",
            "title": "Jev Decision Engine Underwriting Evaluation",
            "message": f"Verdict: {latest_run.salary_status}. Recommended employer: '{latest_run.detected_employer or 'N/A'}'. Human review required: {latest_run.requires_human_review}. Rationale: {latest_run.explanation[:200]}...",
            "metadata": {
                "salary_status": latest_run.salary_status,
                "detected_employer": latest_run.detected_employer,
                "requires_human_review": latest_run.requires_human_review,
                "reason_codes": latest_run.reason_codes,
                "uncertainties": latest_run.uncertainties,
            }
        })

    # 6. Excel 5-Sheet Workbook Generation
    if statement.workbook_status == "completed":
        logs.append({
            "timestamp": statement.workbook_generated_at.isoformat() if statement.workbook_generated_at else (statement.updated_at.isoformat() if statement.updated_at else ""),
            "stage": "REPORTING",
            "level": "SUCCESS",
            "title": "5-Sheet Excel Workbook Finalized",
            "message": "Generated standardized 5-sheet financial audit workbook in INR (Summary, Bank_Account_holder_info, Bank_Txns, Salary_Analysis_Txns, Salary_Results).",
            "metadata": {
                "workbook_status": statement.workbook_status,
                "reporting_currency": "INR",
            }
        })

    # Add audit log entries
    for a in audits:
        if a.action not in ["STATEMENT_UPLOADED"]:
            logs.append({
                "timestamp": a.created_at.isoformat() if a.created_at else "",
                "stage": "AUDIT",
                "level": "INFO",
                "title": a.action.replace("_", " ").title(),
                "message": f"Action {a.action} recorded in audit ledger.",
                "metadata": a.details_json or {},
            })

    # If still processing
    if statement.status == "processing":
        logs.append({
            "timestamp": statement.updated_at.isoformat() if statement.updated_at else "",
            "stage": "PROCESSING",
            "level": "INFO",
            "title": "Pipeline Actively Executing",
            "message": "Background worker is currently processing document pages, extracting transactions, and computing salary candidates.",
            "metadata": {
                "current_status": "processing",
                "extracted_so_far": statement.total_transactions_count,
            }
        })

    return {
        "statement_id": str(statement.id),
        "status": statement.status,
        "filename": statement.filename,
        "logs": logs,
    }
