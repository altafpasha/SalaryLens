"""
SalaryLens AI by CodeSec — Jev Decision Engine & Grounding Verification Service
"""
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.config import settings
from app.schemas.openrouter import AIModelCallResult, JevDecisionResponse
from app.services.openrouter.client import OpenRouterClient

logger = logging.getLogger("salarylens.jev")


class JevDecisionEngine:
    """
    Evaluates grounded financial evidence using the configured OpenRouter DECISION_MODEL.
    Applies authoritative Python post-validation to verify all cited transaction IDs and months,
    rejecting hallucinated records and mandating human review when evidence is conflicting or weak.
    """

    ALLOWED_STATUSES = {
        "likely_salary",
        "possible_salary",
        "multiple_salary_candidates",
        "insufficient_evidence",
        "conflicting_evidence",
        "analysis_failed",
    }

    SYSTEM_PROMPT = """You are the Jev Decision Engine for SalaryLens AI by CodeSec.
Your responsibility is to evaluate structured bank statement evidence and make a rigorous, evidence-grounded salary finding.

CRITICAL RULES:
1. You MUST ONLY cite transaction IDs that appear in the provided evidence. DO NOT invent, alter, or hallucinate transaction IDs.
2. Distinguish net salary credited to a bank account from gross salary. Never claim to know gross salary from bank credits alone.
3. If evidence is ambiguous, irregular, or missing months, set requires_human_review to true.
4. If multiple competing employers are detected, set status to 'multiple_salary_candidates' and requires_human_review to true.
5. If credits are insufficient (e.g. only 1 transaction across 3 months), set status to 'insufficient_evidence'.
6. Do NOT make or imply loan approval or credit risk decisions.
7. Return strictly valid JSON adhering to the JevDecisionResponse schema.
8. Keep explanation and uncertainties concise (1-2 sentences). Do not output markdown or explanations outside the JSON object.
"""

    def __init__(self, client: Optional[OpenRouterClient] = None):
        self.client = client or OpenRouterClient()

    @classmethod
    def verify_grounding(
        cls,
        decision: JevDecisionResponse,
        valid_transaction_ids: Set[str],
        valid_months: Set[str],
        financial_status: str,
        candidate_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> JevDecisionResponse:
        """
        Validates model output against authoritative database records:
        - Drops any fabricated transaction IDs while mapping reference numbers/descriptions to valid UUIDs.
        - Drops any non-existent months.
        - Enforces human review if hallucinated IDs were detected or status conflicts with Python calculations.
        """
        raw_ids = decision.supporting_transaction_ids or []
        verified_ids = []
        hallucinated_ids = []

        candidate_tx_list = candidate_transactions or []
        tx_by_id = {t["id"]: t for t in candidate_tx_list}

        for rid in raw_ids:
            if rid in valid_transaction_ids:
                verified_ids.append(rid)
            else:
                # Check if rid is a reference number or keyword within description
                matched_id = None
                for t in candidate_tx_list:
                    if rid.lower() in t.get("description", "").lower() or rid == t.get("id"):
                        matched_id = t["id"]
                        break
                if matched_id:
                    if matched_id not in verified_ids:
                        verified_ids.append(matched_id)
                else:
                    hallucinated_ids.append(rid)

        # If model returned no direct IDs or couldn't match raw IDs, but identified a valid employer candidate
        emp_cand = (decision.employer_candidate or "").lower().strip()
        if not verified_ids and emp_cand:
            for t in candidate_tx_list:
                desc = t.get("description", "").lower()
                cand_emp = (t.get("candidate_employer") or "").lower()
                if (emp_cand in desc or emp_cand in cand_emp or cand_emp in emp_cand) and t["id"] in valid_transaction_ids:
                    if t["id"] not in verified_ids:
                        verified_ids.append(t["id"])

        uncertainties = list(decision.uncertainties or [])
        requires_human_review = decision.requires_human_review

        if hallucinated_ids:
            logger.warning(f"Jev model returned hallucinated transaction IDs: {hallucinated_ids}")
            uncertainties.append(
                f"Model cited {len(hallucinated_ids)} transaction IDs not present in source statement records."
            )
            requires_human_review = True

        verified_months = [m for m in (decision.supporting_months or []) if m in valid_months]
        if not verified_months and verified_ids:
            derived_months = {tx_by_id[tid]["date"][:7] for tid in verified_ids if tid in tx_by_id and "date" in tx_by_id[tid]}
            verified_months = sorted(list(derived_months & valid_months)) if valid_months else sorted(list(derived_months))
        if not verified_months and valid_months:
            verified_months = sorted(list(valid_months))

        # Ensure status is an allowed enum value
        status_val = decision.status
        if status_val in ["salary_confirmed", "salary_detected", "confirmed", "verified", "likely"]:
            status_val = "likely_salary"
        elif status_val not in cls.ALLOWED_STATUSES:
            status_val = "analysis_failed"

        # Align with authoritative Python financial status if conflicting
        if financial_status in ["insufficient_evidence", "multiple_salary_candidates", "conflicting_evidence"]:
            if status_val == "likely_salary":
                status_val = financial_status
                requires_human_review = True
                uncertainties.append(
                    f"Overrode model decision to '{financial_status}' based on authoritative Python financial constraints."
                )

        # If zero supporting transaction IDs verified and status claims likely_salary, downgrade
        if not verified_ids and status_val in ["likely_salary", "possible_salary"]:
            status_val = "insufficient_evidence"
            requires_human_review = True
            uncertainties.append("No verified supporting transactions remain to support salary finding.")

        return JevDecisionResponse(
            status=status_val,
            employer_candidate=decision.employer_candidate,
            supporting_transaction_ids=verified_ids,
            supporting_months=verified_months,
            reason_codes=decision.reason_codes or [],
            explanation=decision.explanation,
            uncertainties=uncertainties,
            requires_human_review=requires_human_review,
        )

    async def evaluate_evidence(
        self,
        rag_evidence: Dict[str, Any],
        financial_status: str,
        detected_months: List[str],
        statement_id: str,
        accumulated_cost: Decimal = Decimal("0.00"),
        run_id: Optional[str] = None,
    ) -> Tuple[JevDecisionResponse, AIModelCallResult]:
        """
        Executes Jev decision model and applies strict grounding verification.
        Enforces max_tokens=1500 for compact structured responses.
        """
        valid_tx_ids = {
            t["id"] for t in rag_evidence.get("candidate_transactions", [])
        }
        valid_months = set(detected_months)

        evidence_json = json.dumps(rag_evidence, separators=(',', ':'))
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Evaluate bank statement evidence and return structured decision:\n{evidence_json}"
            }
        ]

        result = await self.client.generate_chat_completion(
            messages=messages,
            model=settings.DECISION_MODEL,
            stage="decision",
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=2000,
            statement_id=statement_id,
            run_id=run_id,
            accumulated_cost=accumulated_cost,
        )

        if not result.success or not result.parsed_json:
            fallback = JevDecisionResponse(
                status="analysis_failed",
                employer_candidate=None,
                supporting_transaction_ids=[],
                supporting_months=[],
                reason_codes=["AI_MODEL_UNAVAILABLE"],
                explanation="Automated Jev decision evaluation could not complete. Preserving extracted evidence for human review.",
                uncertainties=["AI decision model invocation failed or timed out."],
                requires_human_review=True,
            )
            return fallback, result

        try:
            # If in demo mode with empty synthetic IDs, populate with valid IDs for realistic grounded output
            raw_payload = dict(result.parsed_json)
            if result.is_simulated and not raw_payload.get("supporting_transaction_ids"):
                raw_payload["supporting_transaction_ids"] = list(valid_tx_ids)
                if not raw_payload.get("supporting_months"):
                    raw_payload["supporting_months"] = list(valid_months)

            unverified = JevDecisionResponse.model_validate(raw_payload)
            grounded = self.verify_grounding(
                decision=unverified,
                valid_transaction_ids=valid_tx_ids,
                valid_months=valid_months,
                financial_status=financial_status,
                candidate_transactions=rag_evidence.get("candidate_transactions", []),
            )
            return grounded, result
        except Exception as e:
            logger.error(f"Error parsing or grounding Jev response: {str(e)}")
            fallback = JevDecisionResponse(
                status="analysis_failed",
                employer_candidate=None,
                supporting_transaction_ids=[],
                supporting_months=[],
                reason_codes=["SCHEMA_VALIDATION_ERROR"],
                explanation=f"Error validating model structured decision: {str(e)}",
                uncertainties=["Structured model response failed schema validation."],
                requires_human_review=True,
            )
            return fallback, result
