"""
SalaryLens AI by CodeSec — RAG Evidence Retrieval Service
"""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.salary_candidate import SalaryCandidateGroup
from app.models.employer_alias import EmployerAlias


class RAGEvidenceRetriever:
    """
    Retrieves grounded structured transaction evidence, historical candidate patterns,
    and approved employer aliases. All retrieval is strictly tenant-isolated and statement-scoped.
    """

    @classmethod
    async def retrieve_statement_evidence(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        statement_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Executes structured SQL queries to compile deterministic evidence for Jev decision model.
        Guarantees strict tenant isolation by scoping all queries to organization_id and statement_id.
        """
        # 1. Fetch Statement metadata
        stmt_q = await db.execute(
            select(Statement).where(
                Statement.id == statement_id,
                Statement.organization_id == organization_id,
            )
        )
        statement = stmt_q.scalar_one_or_none()
        if not statement:
            raise ValueError(f"Statement {statement_id} not found for organization {organization_id}")

        # 2. Fetch candidate groups
        group_q = await db.execute(
            select(SalaryCandidateGroup).where(
                SalaryCandidateGroup.statement_id == statement_id,
                SalaryCandidateGroup.organization_id == organization_id,
            )
        )
        groups = group_q.scalars().all()

        # 3. Fetch candidate transactions (scoped strictly to filtered salary-analysis dataset)
        tx_q = await db.execute(
            select(Transaction).where(
                Transaction.statement_id == statement_id,
                Transaction.organization_id == organization_id,
                Transaction.included_in_salary_analysis == True,
            ).order_by(Transaction.transaction_date.asc())
        )
        candidate_txs = tx_q.scalars().all()
        # If any are explicitly flagged as candidate salary credits, prioritize them for compact tokens
        flagged_candidates = [t for t in candidate_txs if t.is_salary_candidate]
        if flagged_candidates:
            candidate_txs = flagged_candidates

        # 4. Fetch known employer aliases for this tenant
        alias_q = await db.execute(
            select(EmployerAlias).where(
                EmployerAlias.organization_id == organization_id
            )
        )
        aliases = alias_q.scalars().all()
        alias_dict = {a.alias.upper(): a.canonical_name for a in aliases}

        # Build structured RAG evidence package prioritizing top candidate groups
        # Sort groups: primary first, then months_count descending, then transaction_count descending
        sorted_groups = sorted(
            groups,
            key=lambda g: (g.is_primary, g.months_count, g.transaction_count, g.recurrence_score),
            reverse=True
        )[:5]

        evidence_groups = []
        top_employer_names = set()
        for g in sorted_groups:
            top_employer_names.add(g.employer_name.upper())
            evidence_groups.append({
                "employer_name": g.employer_name[:60],
                "canonical_match": alias_dict.get(g.employer_name.upper()),
                "aliases": (g.aliases or [])[:3],
                "transaction_count": g.transaction_count,
                "months_count": g.months_count,
                "missing_months": g.missing_months or [],
                "average_amount": str(g.average_amount),
                "median_amount": str(g.median_amount),
                "min_amount": str(g.min_amount),
                "max_amount": str(g.max_amount),
                "amount_variation_pct": str(g.amount_variation_pct),
                "recurrence_score": str(g.recurrence_score),
                "is_primary": g.is_primary,
            })

        matched_txs = [
            t for t in candidate_txs
            if (t.candidate_employer and t.candidate_employer.upper() in top_employer_names)
            or t.is_salary_candidate
        ]
        if not matched_txs:
            matched_txs = list(candidate_txs)

        evidence_txs = []
        for tx in matched_txs[:25]:
            evidence_txs.append({
                "id": str(tx.id),
                "date": tx.transaction_date.isoformat(),
                "description": tx.raw_description[:75].strip(),
                "credit_amount": str(tx.credit_amount) if tx.credit_amount else "0.00",
                "candidate_employer": tx.candidate_employer,
            })

        return {
            "statement_id": str(statement.id),
            "duration_months": statement.duration_months,
            "candidate_groups": evidence_groups,
            "candidate_transactions": evidence_txs,
            "known_employer_aliases": list(alias_dict.keys())[:10],
        }
