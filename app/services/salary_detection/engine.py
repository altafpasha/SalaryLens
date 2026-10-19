"""
SalaryLens AI by CodeSec — Authoritative Python Financial Validation Engine
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from app.services.salary_detection.normalizer import EmployerNormalizer


@dataclass
class ValidatedCandidateGroup:
    employer_name: str
    aliases: List[str]
    transactions: List[Dict]
    transaction_ids: List[str]
    months: List[str]
    missing_months: List[str]
    average_amount: Decimal
    median_amount: Decimal
    min_amount: Decimal
    max_amount: Decimal
    amount_variation_pct: Decimal
    recurrence_score: Decimal
    is_primary: bool = False


@dataclass
class FinancialValidationResult:
    has_salary_candidates: bool
    status: str  # likely_salary, possible_salary, multiple_salary_candidates, insufficient_evidence, conflicting_evidence
    candidate_groups: List[ValidatedCandidateGroup] = field(default_factory=list)
    reversals_detected: List[str] = field(default_factory=list)
    duplicates_detected: List[str] = field(default_factory=list)
    detected_statement_months: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FinancialValidationEngine:
    """
    Performs authoritative, deterministic mathematical and chronological calculations
    on extracted transactions using Decimal precision.
    """

    REVERSAL_KEYWORDS = ["REVERSAL", "RETURN", "REFUND", "BOUNCE", "CHARGEBACK", "REV "]

    @classmethod
    def calculate_median(cls, numbers: List[Decimal]) -> Decimal:
        """Calculates exact median using Decimal."""
        if not numbers:
            return Decimal("0.00")
        sorted_nums = sorted(numbers)
        n = len(sorted_nums)
        mid = n // 2
        if n % 2 == 1:
            return sorted_nums[mid]
        else:
            return ((sorted_nums[mid - 1] + sorted_nums[mid]) / Decimal("2")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    @classmethod
    def detect_duplicates_and_reversals(
        cls,
        transactions: List[Dict]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Identifies duplicate transactions and reversed/refunded credits.
        Returns (duplicate_indices_or_ids, reversal_transaction_ids).
        """
        duplicate_ids: Set[str] = set()
        reversed_ids: Set[str] = set()

        seen_keys: Dict[Tuple, str] = {}
        credits = []
        debits = []

        for tx in transactions:
            tx_id = str(tx.get("id", ""))
            tx_date = str(tx.get("transaction_date"))
            credit = tx.get("credit_amount")
            debit = tx.get("debit_amount")
            desc = str(tx.get("raw_description") or tx.get("description", "")).strip().upper()

            # 1. Exact Duplicate Check (same date, same credit amount, same description)
            if credit is not None and credit > 0:
                key = (tx_date, str(credit), desc)
                if key in seen_keys:
                    duplicate_ids.add(tx_id)
                else:
                    seen_keys[key] = tx_id
                credits.append((tx_id, tx_date, credit, desc))
            elif debit is not None and debit > 0:
                debits.append((tx_id, tx_date, debit, desc))

        # 2. Reversal / Chargeback Check
        for deb_id, deb_date, deb_amt, deb_desc in debits:
            is_rev_narration = any(kw in deb_desc for kw in cls.REVERSAL_KEYWORDS)
            if is_rev_narration:
                # Find matching credit with same or nearly same amount
                for cred_id, cred_date, cred_amt, cred_desc in credits:
                    if cred_amt == deb_amt:
                        reversed_ids.add(cred_id)
                        reversed_ids.add(deb_id)

        return duplicate_ids, reversed_ids

    @classmethod
    def get_month_span(cls, dates: List[date]) -> List[str]:
        """Returns sorted list of all calendar months spanned from min_date to max_date."""
        if not dates:
            return []
        min_d = min(dates)
        max_d = max(dates)

        months = []
        cur_year = min_d.year
        cur_month = min_d.month

        while (cur_year < max_d.year) or (cur_year == max_d.year and cur_month <= max_d.month):
            months.append(f"{cur_year:04d}-{cur_month:02d}")
            if cur_month == 12:
                cur_month = 1
                cur_year += 1
            else:
                cur_month += 1
        return months

    @classmethod
    def analyze_transactions(
        cls,
        transactions: List[Dict],
        duration_months_hint: Optional[int] = None
    ) -> FinancialValidationResult:
        """
        Main authoritative financial validation pipeline.
        transactions is a list of dicts with:
        id, transaction_date (date or YYYY-MM-DD str), raw_description,
        credit_amount (Decimal), debit_amount (Decimal), candidate_employer, is_salary_candidate
        """
        if not transactions:
            return FinancialValidationResult(
                has_salary_candidates=False,
                status="insufficient_evidence",
                warnings=["Statement contains no extracted transactions."]
            )

        # Parse dates and clean types
        parsed_txs = []
        all_dates: List[date] = []

        for tx in transactions:
            d_val = tx.get("transaction_date")
            if isinstance(d_val, str):
                parsed_d = datetime.strptime(d_val[:10], "%Y-%m-%d").date()
            elif isinstance(d_val, date):
                parsed_d = d_val
            else:
                continue

            credit = tx.get("credit_amount")
            if credit is not None and not isinstance(credit, Decimal):
                credit = Decimal(str(credit))

            debit = tx.get("debit_amount")
            if debit is not None and not isinstance(debit, Decimal):
                debit = Decimal(str(debit))

            item = dict(tx)
            item["date_obj"] = parsed_d
            item["credit_amount"] = credit
            item["debit_amount"] = debit
            parsed_txs.append(item)
            all_dates.append(parsed_d)

        # Detect duplicates and reversals
        duplicate_ids, reversal_ids = cls.detect_duplicates_and_reversals(parsed_txs)

        # Statement calendar month span
        span_months = cls.get_month_span(all_dates)
        expected_month_count = duration_months_hint or len(span_months) or 3

        # Filter potential salary credits:
        # Must be incoming credit, non-zero, not a reversal, not a duplicate
        candidates = []
        for tx in parsed_txs:
            tx_id = str(tx.get("id", ""))
            credit = tx.get("credit_amount")
            debit = tx.get("debit_amount")

            # Check credit direction: Must be positive incoming credit
            if credit is None or credit <= Decimal("0.00"):
                continue

            # Exclude debit directions or reversals/duplicates
            if debit is not None and debit > credit:
                continue
            if tx_id in reversal_ids or tx_id in duplicate_ids:
                continue

            candidates.append(tx)

        if not candidates:
            return FinancialValidationResult(
                has_salary_candidates=False,
                status="insufficient_evidence",
                reversals_detected=list(reversal_ids),
                duplicates_detected=list(duplicate_ids),
                detected_statement_months=span_months,
                warnings=["No incoming credit transactions qualifying as salary candidates were found."]
            )

        # Cluster candidate transactions by normalized employer / pattern
        clusters: Dict[str, List[Dict]] = {}
        for cand in candidates:
            emp_name = cand.get("candidate_employer") or cand.get("potential_employer")
            clean_name = EmployerNormalizer.extract_clean_employer_name(
                cand.get("raw_description") or cand.get("description", ""), emp_name
            )
            # Find existing cluster if similar
            matched_key = None
            for key in clusters.keys():
                if EmployerNormalizer.are_employers_similar(key, clean_name):
                    matched_key = key
                    break

            if matched_key:
                clusters[matched_key].append(cand)
            else:
                clusters[clean_name] = [cand]

        candidate_groups: List[ValidatedCandidateGroup] = []

        for emp_name, tx_list in clusters.items():
            tx_ids = [str(t.get("id")) for t in tx_list]
            amounts = [t["credit_amount"] for t in tx_list]
            tx_dates = [t["date_obj"] for t in tx_list]
            months_present = sorted(list({f"{d.year:04d}-{d.month:02d}" for d in tx_dates}))

            # Missing months calculation
            missing = [m for m in span_months if m not in months_present]

            # Authoritative Decimal metrics
            avg_amount = (sum(amounts) / Decimal(str(len(amounts)))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            med_amount = cls.calculate_median(amounts)
            min_amount = min(amounts).quantize(Decimal("0.01"))
            max_amount = max(amounts).quantize(Decimal("0.01"))

            # Variation percentage: ((max - min) / average) * 100
            if avg_amount > 0:
                var_pct = (((max_amount - min_amount) / avg_amount) * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                var_pct = Decimal("0.00")

            # Recurrence scoring (0.000 to 1.000)
            # 1. Month coverage: months_present / expected_month_count
            coverage_ratio = Decimal(str(len(months_present))) / Decimal(str(max(expected_month_count, 1)))
            coverage_ratio = min(coverage_ratio, Decimal("1.00"))

            # 2. Amount stability: lower variation yields higher score
            if var_pct <= Decimal("2.00"):
                stability_score = Decimal("1.00")
            elif var_pct <= Decimal("15.00"):
                stability_score = Decimal("0.85")
            elif var_pct <= Decimal("30.00"):
                stability_score = Decimal("0.60")
            else:
                stability_score = Decimal("0.30")

            # 3. Monthly cadence score: each month should ideally have 1 (or 2 if bi-weekly) credits
            avg_per_month = Decimal(str(len(tx_list))) / Decimal(str(max(len(months_present), 1)))
            cadence_score = Decimal("1.00") if (Decimal("0.8") <= avg_per_month <= Decimal("2.2")) else Decimal("0.50")

            recurrence_score = (
                (coverage_ratio * Decimal("0.50")) +
                (stability_score * Decimal("0.35")) +
                (cadence_score * Decimal("0.15"))
            ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

            # Collect raw aliases
            raw_aliases = list({
                t.get("raw_description", "") for t in tx_list if t.get("raw_description")
            })

            candidate_groups.append(
                ValidatedCandidateGroup(
                    employer_name=emp_name or "UNIDENTIFIED EMPLOYER",
                    aliases=raw_aliases,
                    transactions=tx_list,
                    transaction_ids=tx_ids,
                    months=months_present,
                    missing_months=missing,
                    average_amount=avg_amount,
                    median_amount=med_amount,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    amount_variation_pct=var_pct,
                    recurrence_score=recurrence_score,
                    is_primary=False,
                )
            )

        # Sort candidate groups by recurrence score descending, then by month count
        candidate_groups.sort(
            key=lambda g: (g.recurrence_score, len(g.months), g.average_amount),
            reverse=True
        )

        # Determine overall financial validation status
        warnings = []
        if not candidate_groups:
            overall_status = "insufficient_evidence"
        else:
            primary = candidate_groups[0]
            # Check for multiple competing candidates
            competing_groups = [
                g for g in candidate_groups[1:]
                if g.recurrence_score >= Decimal("0.650") and len(g.months) >= 2
            ]

            if competing_groups:
                overall_status = "multiple_salary_candidates"
                warnings.append(
                    f"Multiple potential employers detected with recurring credits: "
                    f"{primary.employer_name} and {competing_groups[0].employer_name}."
                )
            elif primary.recurrence_score >= Decimal("0.750") and len(primary.months) >= 2:
                primary.is_primary = True
                if len(primary.missing_months) > 0:
                    overall_status = "possible_salary"
                    warnings.append(f"Salary credits detected but missing month(s): {', '.join(primary.missing_months)}.")
                else:
                    overall_status = "likely_salary"
            elif primary.recurrence_score >= Decimal("0.450") and len(primary.months) >= 2:
                primary.is_primary = True
                overall_status = "possible_salary"
                warnings.append("Partial or irregular recurring salary pattern detected.")
            else:
                overall_status = "insufficient_evidence"
                warnings.append("Insufficient evidence to reliably establish recurring salary credits.")

        return FinancialValidationResult(
            has_salary_candidates=len(candidate_groups) > 0,
            status=overall_status,
            candidate_groups=candidate_groups,
            reversals_detected=list(reversal_ids),
            duplicates_detected=list(duplicate_ids),
            detected_statement_months=span_months,
            warnings=warnings,
        )
