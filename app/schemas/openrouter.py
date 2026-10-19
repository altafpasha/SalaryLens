"""
SalaryLens AI by CodeSec — OpenRouter Schemas & Structured Model Payloads
"""
from datetime import date
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator


class ExtractedRawTransaction(BaseModel):
    transaction_date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    value_date: Optional[str] = Field(None, description="Optional settlement/value date")
    description: str = Field(..., description="Exact raw transaction description from document")
    credit_amount: Optional[Decimal] = Field(None, description="Incoming credit amount (positive)")
    debit_amount: Optional[Decimal] = Field(None, description="Outgoing debit amount (positive)")
    balance: Optional[Decimal] = Field(None, description="Running balance if printed")
    currency: str = Field("USD", description="Currency code (e.g. USD, EUR, GBP)")
    page_number: int = Field(1, description="Page number where transaction was found")
    potential_employer: Optional[str] = Field(None, description="Likely employer name identified from description")
    employer_aliases: List[str] = Field(default_factory=list, description="Extracted employer abbreviations or aliases")
    is_salary_candidate: bool = Field(False, description="Whether this credit matches a potential salary pattern")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Model confidence score")
    notes: Optional[str] = Field(None, description="Notes on ambiguity or possible reversals")

    @model_validator(mode="before")
    @classmethod
    def clean_raw_transaction(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        # Normalize description
        if not data.get("description"):
            for k in ["raw_description", "particulars", "narration", "memo", "details", "desc"]:
                if data.get(k):
                    data["description"] = str(data[k])
                    break
            if not data.get("description"):
                data["description"] = "UNLABELED TRANSACTION"

        # Clean monetary amounts
        for amt_field in ["credit_amount", "debit_amount", "balance"]:
            val = data.get(amt_field)
            if val is not None:
                if isinstance(val, (int, float)):
                    data[amt_field] = Decimal(str(val))
                elif isinstance(val, str):
                    cleaned = val.replace("$", "").replace("₹", "").replace(",", "").strip()
                    if cleaned in ["", "-", "None", "null"]:
                        data[amt_field] = None
                    else:
                        try:
                            data[amt_field] = Decimal(cleaned)
                        except Exception:
                            data[amt_field] = None

        # Normalize potential_employer
        if "potential_employer" in data and data["potential_employer"] is not None:
            if isinstance(data["potential_employer"], list):
                data["potential_employer"] = str(data["potential_employer"][0]) if data["potential_employer"] else None
            elif not isinstance(data["potential_employer"], str):
                data["potential_employer"] = str(data["potential_employer"])

        # Normalize employer_aliases
        if "employer_aliases" in data and data["employer_aliases"] is not None:
            if isinstance(data["employer_aliases"], str):
                data["employer_aliases"] = [a.strip() for a in data["employer_aliases"].split(",") if a.strip()]
            elif not isinstance(data["employer_aliases"], list):
                data["employer_aliases"] = [str(data["employer_aliases"])]

        # Normalize confidence
        if "confidence" in data and data["confidence"] is not None:
            try:
                conf = float(data["confidence"])
                data["confidence"] = max(0.0, min(1.0, conf))
            except Exception:
                data["confidence"] = 0.0

        return data


class ExtractedStatementPayload(BaseModel):
    account_holder: Optional[str] = Field(None, description="Extracted account holder name")
    account_number_last4: Optional[str] = Field(None, description="Last 4 digits of account number")
    detected_statement_period: Optional[str] = Field(None, description="Statement period (e.g. 2026-03 to 2026-05)")
    transactions: List[ExtractedRawTransaction] = Field(default_factory=list, description="Extracted transactions")
    uncertainties: List[str] = Field(default_factory=list, description="Ambiguities or unreadable sections noted by model")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"transactions": data}
        if isinstance(data, dict):
            if "transactions" not in data:
                for k in ["items", "data", "records", "statement_transactions"]:
                    if k in data and isinstance(data[k], list):
                        data["transactions"] = data[k]
                        break
        return data


class JevDecisionResponse(BaseModel):
    status: str = Field(
        default="insufficient_evidence",
        description="One of: likely_salary, possible_salary, multiple_salary_candidates, insufficient_evidence, conflicting_evidence, analysis_failed"
    )
    employer_candidate: Optional[str] = Field(None, description="Identified canonical employer name")
    supporting_transaction_ids: List[str] = Field(default_factory=list, description="Referenced backend transaction UUIDs")
    supporting_months: List[str] = Field(default_factory=list, description="Supported months in YYYY-MM format")
    reason_codes: List[str] = Field(default_factory=list, description="Explainable reason codes")
    explanation: str = Field(default="", description="Comprehensive evidence-based explanation")
    uncertainties: List[str] = Field(default_factory=list, description="Remaining uncertainties or risks")
    requires_human_review: bool = Field(True, description="Whether human review is required")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Normalize explanation
        if not data.get("explanation"):
            for alt_key in ["reasoning", "summary", "description", "details", "notes", "rationale", "analysis", "decision_explanation"]:
                if data.get(alt_key):
                    data["explanation"] = str(data[alt_key])
                    break
            if not data.get("explanation"):
                data["explanation"] = "Evaluated salary evidence and candidate transaction continuity."

        # 2. Normalize employer_candidate
        if data.get("employer_candidate"):
            if isinstance(data["employer_candidate"], dict):
                data["employer_candidate"] = str(
                    data["employer_candidate"].get("employer_name")
                    or data["employer_candidate"].get("name")
                    or data["employer_candidate"].get("employer")
                    or ""
                )
            elif not isinstance(data["employer_candidate"], str):
                data["employer_candidate"] = str(data["employer_candidate"])
        else:
            for alt_emp in ["primary_employer", "employer_name", "employer", "company_name", "company", "detected_employer"]:
                if data.get(alt_emp):
                    if isinstance(data[alt_emp], dict):
                        data["employer_candidate"] = str(
                            data[alt_emp].get("employer_name")
                            or data[alt_emp].get("name")
                            or data[alt_emp].get("employer")
                            or ""
                        )
                    else:
                        data["employer_candidate"] = str(data[alt_emp])
                    break

        # 3. Normalize supporting_transaction_ids
        if not data.get("supporting_transaction_ids"):
            collected_ids = []
            # Check nested net_salary_findings
            nsf = data.get("net_salary_findings")
            if isinstance(nsf, dict):
                for rsc in nsf.get("recurring_salary_credits", []):
                    if isinstance(rsc, dict) and rsc.get("transaction_id"):
                        collected_ids.append(str(rsc["transaction_id"]))
            # Check nested additional_employer_credits
            aec = data.get("additional_employer_credits")
            if isinstance(aec, dict):
                for tx_item in aec.get("transactions", []):
                    if isinstance(tx_item, dict) and tx_item.get("transaction_id"):
                        collected_ids.append(str(tx_item["transaction_id"]))
            if collected_ids:
                data["supporting_transaction_ids"] = collected_ids
            else:
                for alt_id_key in ["evidence_transaction_ids", "transaction_ids", "supporting_transactions", "supporting_ids"]:
                    if data.get(alt_id_key):
                        data["supporting_transaction_ids"] = data[alt_id_key]
                        break

        # 4. Normalize supporting_months
        if not data.get("supporting_months"):
            nsf = data.get("net_salary_findings")
            if isinstance(nsf, dict) and nsf.get("salary_months_covered"):
                data["supporting_months"] = nsf["salary_months_covered"]

        # 5. Normalize status
        if data.get("status"):
            st = str(data["status"]).lower().strip().replace(" ", "_").replace("-", "_")
            if any(w in st for w in ["detect", "confirm", "verif", "likely", "success", "identif"]):
                st = "likely_salary"
            elif any(w in st for w in ["possib", "unconfirm"]):
                st = "possible_salary"
            elif any(w in st for w in ["multiple", "compet"]):
                st = "multiple_salary_candidates"
            elif any(w in st for w in ["insuffic", "no_salary", "not_found", "none"]):
                st = "insufficient_evidence"
            elif any(w in st for w in ["conflict", "discrepan"]):
                st = "conflicting_evidence"
            data["status"] = st

        # 5. Normalize lists of strings
        for list_field in ["supporting_transaction_ids", "supporting_months", "reason_codes", "uncertainties"]:
            val = data.get(list_field)
            if val is not None:
                if isinstance(val, list):
                    data[list_field] = [str(x) for x in val if x is not None]
                elif isinstance(val, str):
                    data[list_field] = [val] if val else []

        # 6. Normalize requires_human_review
        if "requires_human_review" in data:
            if isinstance(data["requires_human_review"], str):
                data["requires_human_review"] = data["requires_human_review"].lower() in ["true", "1", "yes"]

        return data


class AIModelCallResult(BaseModel):
    model_name: str
    stage: str
    raw_response: dict
    parsed_json: Optional[dict] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    provider_cost_usd: Optional[Decimal] = None
    estimated_cost_usd: Decimal = Decimal("0.000000")
    latency_ms: int = 0
    retry_count: int = 0
    is_simulated: bool = False
    success: bool = True
    error_message: Optional[str] = None
    actual_model: Optional[str] = None
    statement_id: Optional[str] = None
    run_id: Optional[str] = None
    is_cache_hit: bool = False
