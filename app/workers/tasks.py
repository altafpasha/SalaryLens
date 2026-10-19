"""
SalaryLens AI by CodeSec — Asynchronous Statement Processing & Retention Tasks
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.salary_candidate import SalaryCandidateGroup, SalaryCandidate
from app.models.analysis_run import AnalysisRun
from app.models.model_usage import ModelUsageEvent
from app.models.retention import RetentionJob
from app.services.document_processing.extractor import DocumentExtractor
from app.services.document_processing.storage import StorageService
from app.services.document_processing.account_info import AccountInfoExtractor
from app.services.transaction_extraction.extractor import SalaryFinderService
from app.services.salary_detection.engine import FinancialValidationEngine
from app.services.salary_detection.filter import TransactionFilterService
from app.services.retrieval.rag import RAGEvidenceRetriever
from app.services.decision_engine.jev import JevDecisionEngine
from app.services.reporting.workbook import ExcelWorkbookGenerator
from app.workers.celery_app import celery_app

logger = logging.getLogger("salarylens.tasks")


async def run_statement_processing_pipeline(statement_id_str: str, organization_id_str: str) -> bool:
    """
    Executes the end-to-end SalaryLens AI statement analysis pipeline.
    """
    stmt_id = uuid.UUID(statement_id_str)
    org_id = uuid.UUID(organization_id_str)
    run_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        # 1. Fetch statement & verify idempotency
        stmt_q = await db.execute(
            select(Statement).where(
                Statement.id == stmt_id,
                Statement.organization_id == org_id,
            )
        )
        statement = stmt_q.scalar_one_or_none()
        if not statement:
            logger.error(f"Statement {stmt_id} not found for organization {org_id}.")
            return False

        if statement.status in ["completed", "requires_human_review"] and statement.workbook_status == "completed":
            logger.info(f"Statement {stmt_id} already fully processed. Skipping.")
            return True

        statement.status = "processing"
        await db.commit()

        initial_wb_created = False
        workbook_path = StorageService.get_statement_workbook_path(org_id, stmt_id)

        try:
            # 2. Document Processing & Text Extraction
            render_dir = StorageService.get_statement_render_dir(org_id, stmt_id)
            doc_result = DocumentExtractor.extract_document(
                file_path=statement.file_path,
                render_dir=render_dir,
            )
            statement.is_scanned = doc_result.is_scanned
            statement.page_count = doc_result.total_pages
            statement.native_pages_count = doc_result.native_pages_count
            statement.ocr_pages_count = doc_result.ocr_pages_count
            statement.account_info_json = doc_result.account_info

            # Parse start and end dates from account info if available
            if doc_result.account_info.get("start_date"):
                for fmt in ["%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        statement.statement_start_date = datetime.strptime(doc_result.account_info["start_date"][:10], fmt).date()
                        break
                    except Exception:
                        pass
            if doc_result.account_info.get("end_date"):
                for fmt in ["%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        statement.statement_end_date = datetime.strptime(doc_result.account_info["end_date"][:10], fmt).date()
                        break
                    except Exception:
                        pass

            await db.commit()

            # 3. OpenRouter Salary Finder Transaction Extraction
            accumulated_cost = Decimal("0.00")
            salary_finder = SalaryFinderService()
            extracted_payload, extraction_usage = await salary_finder.extract_transactions(
                statement_text=doc_result.full_text,
                statement_id=str(stmt_id),
                table_transactions=doc_result.table_transactions,
                accumulated_cost=accumulated_cost,
                run_id=str(run_id),
            )
            accumulated_cost += (extraction_usage.provider_cost_usd or extraction_usage.estimated_cost_usd)

            # 4. Deterministic Transaction Filtering & Direction Safeguards
            raw_tx_dicts = []
            for raw_tx in extracted_payload.transactions:
                raw_tx_dicts.append({
                    "transaction_date": raw_tx.transaction_date,
                    "value_date": raw_tx.value_date,
                    "description": raw_tx.description,
                    "raw_description": raw_tx.description,
                    "credit_amount": raw_tx.credit_amount,
                    "debit_amount": raw_tx.debit_amount,
                    "balance": raw_tx.balance,
                    "currency": raw_tx.currency,
                    "page_number": raw_tx.page_number,
                    "is_salary_candidate": raw_tx.is_salary_candidate,
                    "candidate_employer": raw_tx.potential_employer,
                    "confidence": raw_tx.confidence,
                })

            annotated_txs, filtering_stats = TransactionFilterService.filter_statement_transactions(raw_tx_dicts)

            # Update statement statistics
            statement.total_transactions_count = filtering_stats["total_transactions"]
            statement.total_debit_count = filtering_stats["total_debits"]
            statement.total_credit_count = filtering_stats["total_credits"]
            statement.included_in_salary_count = filtering_stats["included_in_salary_analysis"]
            statement.excluded_from_salary_count = filtering_stats["excluded_from_salary_analysis"]

            # If start/end dates were not parsed from header, infer from transaction date min/max
            tx_dates = [t["transaction_date"][:10] for t in annotated_txs if t.get("transaction_date")]
            if tx_dates and not statement.statement_start_date:
                try:
                    statement.statement_start_date = datetime.strptime(min(tx_dates), "%Y-%m-%d").date()
                except Exception:
                    pass
            if tx_dates and not statement.statement_end_date:
                try:
                    statement.statement_end_date = datetime.strptime(max(tx_dates), "%Y-%m-%d").date()
                except Exception:
                    pass

            # 5. Save Extracted Transactions to Database (preserving ALL transactions)
            # Remove any previously saved transactions for this statement (idempotency)
            existing_tx_q = await db.execute(select(Transaction).where(Transaction.statement_id == stmt_id))
            for old_tx in existing_tx_q.scalars().all():
                await db.delete(old_tx)
            await db.flush()

            db_transactions: list[Transaction] = []
            for item in annotated_txs:
                try:
                    tx_date = datetime.strptime(str(item["transaction_date"])[:10], "%Y-%m-%d").date()
                except Exception:
                    tx_date = datetime.now(timezone.utc).date()

                val_date = None
                if item.get("value_date"):
                    try:
                        val_date = datetime.strptime(str(item["value_date"])[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass

                tx_uuid = uuid.uuid4()
                item["id"] = tx_uuid

                db_tx = Transaction(
                    id=tx_uuid,
                    statement_id=stmt_id,
                    organization_id=org_id,
                    transaction_date=tx_date,
                    value_date=val_date,
                    raw_description=item["description"],
                    normalized_description=item["description"][:500],
                    credit_amount=item.get("credit_amount"),
                    debit_amount=item.get("debit_amount"),
                    balance=item.get("balance"),
                    currency=item.get("currency", "USD"),
                    page_number=item.get("page_number", 1),
                    transaction_direction=item.get("transaction_direction"),
                    category=item.get("category"),
                    extraction_method=item.get("extraction_method", "native"),
                    validation_status=item.get("validation_status", "valid"),
                    validation_warnings=item.get("validation_warnings"),
                    included_in_salary_analysis=item.get("included_in_salary_analysis", False),
                    exclusion_reason=item.get("exclusion_reason"),
                    inclusion_reason=item.get("inclusion_reason"),
                    is_salary_candidate=item.get("is_salary_candidate", False),
                    candidate_employer=item.get("candidate_employer"),
                    confidence=Decimal(str(round(item["confidence"], 3))) if item.get("confidence") is not None else None,
                    metadata_json={
                        "candidate_tier": item.get("candidate_tier"),
                        "ranking_score": item.get("ranking_score"),
                    },
                )
                db.add(db_tx)
                db_transactions.append(db_tx)

            await db.flush()

            # 6. Generate Initial Excel Workbook
            ExcelWorkbookGenerator.generate_initial_workbook(
                statement=statement,
                account_info=doc_result.account_info,
                transactions=annotated_txs,
                filtering_stats=filtering_stats,
                output_path=workbook_path,
                extraction_warnings=doc_result.warnings,
            )
            statement.workbook_file_path = str(workbook_path)
            statement.workbook_status = "initial"
            statement.workbook_validation_status = "verified"
            statement.workbook_generated_at = datetime.now(timezone.utc)
            initial_wb_created = True
            await db.commit()

            # 7. Authoritative Python Financial Validation (using filtered candidate transactions)
            tx_dicts_for_fin = [
                {
                    "id": str(t.id),
                    "transaction_date": t.transaction_date,
                    "raw_description": t.raw_description,
                    "credit_amount": t.credit_amount,
                    "debit_amount": t.debit_amount,
                    "candidate_employer": t.candidate_employer,
                    "is_salary_candidate": t.is_salary_candidate,
                }
                for t in db_transactions
                if t.included_in_salary_analysis
            ]

            fin_result = FinancialValidationEngine.analyze_transactions(
                transactions=tx_dicts_for_fin,
                duration_months_hint=statement.duration_months
            )

            # Mark duplicates and reversals on db transactions
            for t in db_transactions:
                if str(t.id) in fin_result.duplicates_detected:
                    t.is_duplicate = True
                if str(t.id) in fin_result.reversals_detected:
                    t.is_reversal = True
            await db.flush()

            # 8. Save Salary Candidate Groups and Candidates
            # Clean up old candidate groups for idempotency
            old_groups_q = await db.execute(select(SalaryCandidateGroup).where(SalaryCandidateGroup.statement_id == stmt_id))
            for old_grp in old_groups_q.scalars().all():
                await db.delete(old_grp)
            await db.flush()

            saved_candidate_groups: list[SalaryCandidateGroup] = []
            candidate_map = {str(t.id): t for t in db_transactions}
            for group_data in fin_result.candidate_groups:
                candidate_group = SalaryCandidateGroup(
                    statement_id=stmt_id,
                    organization_id=org_id,
                    employer_name=group_data.employer_name,
                    aliases=group_data.aliases,
                    transaction_count=len(group_data.transactions),
                    months_count=len(group_data.months),
                    missing_months=group_data.missing_months,
                    average_amount=group_data.average_amount,
                    median_amount=group_data.median_amount,
                    min_amount=group_data.min_amount,
                    max_amount=group_data.max_amount,
                    amount_variation_pct=group_data.amount_variation_pct,
                    recurrence_score=group_data.recurrence_score,
                    is_primary=group_data.is_primary,
                )
                db.add(candidate_group)
                await db.flush()
                saved_candidate_groups.append(candidate_group)

                for tx_item in group_data.transactions:
                    tx_id_str = str(tx_item.get("id"))
                    matching_tx = candidate_map.get(tx_id_str)
                    if matching_tx:
                        matching_tx.is_salary_candidate = True
                        sc = SalaryCandidate(
                            group_id=candidate_group.id,
                            transaction_id=matching_tx.id,
                            organization_id=org_id,
                            month_label=f"{matching_tx.transaction_date.year:04d}-{matching_tx.transaction_date.month:02d}",
                            day_of_month=matching_tx.transaction_date.day,
                        )
                        db.add(sc)
            await db.flush()

            # 9. RAG Evidence Retrieval (scoped to filtered candidate transactions)
            rag_evidence = await RAGEvidenceRetriever.retrieve_statement_evidence(
                db=db,
                organization_id=org_id,
                statement_id=stmt_id,
            )

            # 10. Jev Decision Model Evaluation
            if len(fin_result.candidate_groups) == 0:
                logger.info(f"No candidate salary groups detected for statement {stmt_id}. Bypassing Jev decision model.")
                decision = JevDecisionResponse(
                    status="insufficient_evidence",
                    employer_candidate=None,
                    supporting_transaction_ids=[],
                    supporting_months=[],
                    reason_codes=["NO_SALARY_CANDIDATE_GROUPS", "INSUFFICIENT_CREDIT_EVIDENCE"],
                    explanation="Authoritative deterministic financial analysis detected zero recurring salary credit groups across the statement period.",
                    uncertainties=["No recurring credits meeting payroll continuity criteria were identified."],
                    requires_human_review=True,
                )
                decision_usage = AIModelCallResult(
                    model_name=settings.DECISION_MODEL,
                    actual_model=settings.DECISION_MODEL,
                    stage="decision",
                    statement_id=str(stmt_id),
                    run_id=str(run_id),
                    raw_response={"bypassed": True, "reason": "No candidate groups detected"},
                    parsed_json=decision.model_dump(),
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    estimated_cost_usd=Decimal("0.00"),
                    provider_cost_usd=Decimal("0.00"),
                    latency_ms=0,
                    retry_count=0,
                    is_simulated=False,
                    is_cache_hit=False,
                    success=True,
                )
            else:
                jev_engine = JevDecisionEngine()
                decision, decision_usage = await jev_engine.evaluate_evidence(
                    rag_evidence=rag_evidence,
                    financial_status=fin_result.status,
                    detected_months=fin_result.detected_statement_months,
                    statement_id=str(stmt_id),
                    accumulated_cost=accumulated_cost,
                    run_id=str(run_id),
                )
            accumulated_cost += (decision_usage.provider_cost_usd or decision_usage.estimated_cost_usd)

            # 11. Persist AnalysisRun & ModelUsageEvents
            total_tokens = extraction_usage.input_tokens + extraction_usage.output_tokens + \
                           decision_usage.input_tokens + decision_usage.output_tokens

            primary_employer = decision.employer_candidate
            if not primary_employer and fin_result.candidate_groups:
                primary_employer = fin_result.candidate_groups[0].employer_name

            # Clean up old analysis runs for idempotency
            old_runs_q = await db.execute(select(AnalysisRun).where(AnalysisRun.statement_id == stmt_id))
            for old_run in old_runs_q.scalars().all():
                await db.delete(old_run)
            await db.flush()

            analysis_run = AnalysisRun(
                statement_id=stmt_id,
                organization_id=org_id,
                status="completed",
                salary_status=decision.status,
                detected_employer=primary_employer,
                supporting_transaction_ids=decision.supporting_transaction_ids,
                supporting_months=decision.supporting_months,
                reason_codes=decision.reason_codes,
                explanation=decision.explanation,
                uncertainties=decision.uncertainties,
                requires_human_review=decision.requires_human_review,
                total_ai_cost_usd=accumulated_cost,
                total_tokens=total_tokens,
                is_demo=extraction_usage.is_simulated or statement.is_demo,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(analysis_run)
            await db.flush()

            for usage_event in [extraction_usage, decision_usage]:
                m_event = ModelUsageEvent(
                    statement_id=stmt_id,
                    analysis_run_id=analysis_run.id,
                    organization_id=org_id,
                    model_name=usage_event.actual_model or usage_event.model_name,
                    stage=usage_event.stage,
                    input_tokens=usage_event.input_tokens,
                    output_tokens=usage_event.output_tokens,
                    cached_tokens=usage_event.cached_tokens,
                    provider_cost_usd=usage_event.provider_cost_usd,
                    estimated_cost_usd=usage_event.estimated_cost_usd,
                    latency_ms=usage_event.latency_ms,
                    retry_count=usage_event.retry_count,
                    is_simulated=usage_event.is_simulated,
                    success=usage_event.success,
                    error_message=usage_event.error_message,
                )
                db.add(m_event)

            # 12. Finalize Excel Workbook with Validated Salary Results
            ExcelWorkbookGenerator.finalize_workbook(
                workbook_path=workbook_path,
                statement=statement,
                candidate_groups=saved_candidate_groups,
                analysis_run=analysis_run,
                transactions=annotated_txs,
                filtering_stats=filtering_stats,
                ai_cost=accumulated_cost,
                ai_tokens=total_tokens,
            )
            statement.workbook_status = "completed"
            statement.workbook_validation_status = "verified"
            statement.workbook_generated_at = datetime.now(timezone.utc)

            # 13. Update Statement Final Status
            if decision.requires_human_review:
                statement.status = "requires_human_review"
            else:
                statement.status = "completed"

            await db.commit()
            logger.info(f"Pipeline successfully completed for statement {stmt_id}. Status: {statement.status}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Error in pipeline for statement {stmt_id}: {str(e)}", exc_info=True)
            async with AsyncSessionLocal() as error_db:
                new_wb_status = "initial_only" if initial_wb_created else "failed"
                new_stmt_status = "requires_human_review" if initial_wb_created else "failed"
                await error_db.execute(
                    update(Statement)
                    .where(Statement.id == stmt_id)
                    .values(
                        status=new_stmt_status,
                        workbook_status=new_wb_status,
                        error_message=str(e)[:500]
                    )
                )
                await error_db.commit()
            return False


@celery_app.task(name="tasks.process_statement_pipeline", bind=True, max_retries=2)
def process_statement_pipeline_task(self, statement_id: str, organization_id: str):
    """Celery task entrypoint."""
    try:
        return asyncio.run(run_statement_processing_pipeline(statement_id, organization_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


async def run_retention_cleanup_async(organization_id_str: Optional[str] = None) -> int:
    """Purges expired statement PDFs in compliance with data retention policies."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DOCUMENT_RETENTION_DAYS)
    deleted_files = 0

    async with AsyncSessionLocal() as db:
        query = select(Statement).where(Statement.created_at < cutoff)
        if organization_id_str:
            query = query.where(Statement.organization_id == uuid.UUID(organization_id_str))

        result = await db.execute(query)
        statements = result.scalars().all()

        for stmt in statements:
            _, count = StorageService.delete_statement_files(stmt.organization_id, stmt.id)
            deleted_files += count

        job = RetentionJob(
            organization_id=uuid.UUID(organization_id_str) if organization_id_str else None,
            status="completed",
            deleted_statements_count=len(statements),
            deleted_files_count=deleted_files,
            executed_at=datetime.now(timezone.utc),
            notes=f"Purged {deleted_files} files older than {settings.DOCUMENT_RETENTION_DAYS} days.",
        )
        db.add(job)
        await db.commit()

    return deleted_files


@celery_app.task(name="tasks.retention_cleanup")
def retention_cleanup_task(organization_id: Optional[str] = None):
    return asyncio.run(run_retention_cleanup_async(organization_id))
