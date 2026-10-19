"""
SalaryLens AI by CodeSec — Statement Lifecycle and Review Routes
"""
import os
import re
import uuid
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
from app.models.human_review import HumanReview
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.statement import (
    CandidateGroupSummary,
    HumanReviewRequest,
    HumanReviewResponse,
    PaginatedTransactionsResponse,
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
    description="Downloads the 5-sheet financial Excel workbook. Requires reviewer, admin, or auditor role."
)
async def download_statement_workbook(
    statement_id: uuid.UUID,
    user_context: tuple[User, uuid.UUID, str] = Depends(require_role("reviewer")),
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

    if not statement.workbook_file_path or not os.path.exists(statement.workbook_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook file is not available for this statement."
        )

    # 3. Log download audit event
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
