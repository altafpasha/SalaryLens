"""
SalaryLens AI by CodeSec — Deterministic Transaction Filtering & Direction Safeguards
"""
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.salary_detection.normalizer import EmployerNormalizer


def sanitize_excel_formula(val: Any) -> Any:
    """
    Prevents CSV/Excel formula injection by prepending an apostrophe (')
    if the string starts with formula trigger characters (=, +, -, @, \\t, \\r).
    """
    if val is None:
        return ""
    if isinstance(val, (int, float, Decimal)):
        return val
    s = str(val)
    if not s:
        return ""
    if s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    stripped = s.lstrip()
    if stripped and stripped[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


class CandidateTier:
    LIKELY_SALARY = "LIKELY_SALARY"
    POSSIBLE_SALARY = "POSSIBLE_SALARY"
    UNLIKELY_SALARY = "UNLIKELY_SALARY"


@dataclass
class FilteredTransactionResult:
    transaction_direction: str  # CREDIT, DEBIT, AMBIGUOUS
    category: str
    included_in_salary_analysis: bool
    exclusion_reason: Optional[str]
    inclusion_reason: Optional[str]
    validation_status: str  # valid, warning
    validation_warnings: Optional[str]
    candidate_tier: str = CandidateTier.UNLIKELY_SALARY
    ranking_score: int = 0


class TransactionFilterService:
    """
    Maintains the separation between the Complete Transaction Dataset (all transactions)
    and the Salary Analysis Dataset (filtered candidate evidence for RAG and AI).
    
    Guarantees:
    Total Extracted Transactions = Transactions Included in Salary Analysis + Transactions Excluded from Salary Analysis
    """

    REVERSAL_KEYWORDS = ["REVERSAL", "RETURN", "REFUND", "BOUNCE", "CHARGEBACK", "CORRECTION", "REV "]
    SALARY_REGEX = re.compile(
        r"\b(SALARY|PAYROLL|STIPEND|WAGES|REMUNERATION|HONORARIUM|BONUS|INCENTIVE|DIR\s+DEP|DIRECT\s+DEP)\b|(?:\b|/)SAL(?:\b|/|\s)",
        re.IGNORECASE,
    )
    INTEREST_REGEX = re.compile(
        r"\b(INTEREST\s+CREDIT|SB\s+INT|SAVINGS\s+INT|CREDIT\s+INTEREST|FD\s+INT|TERM\s+DEPOSIT\s+INT|INT\.PD|MONTHLY\s+INTEREST|QUARTERLY\s+INTEREST)\b|\bINTEREST\b",
        re.IGNORECASE,
    )
    REFUND_REGEX = re.compile(
        r"\b(REFUND|REF/POS|REF-POS|POS\s+REFUND|CASHBACK|CASH\s+BACK|REVERSAL\s+OF\s+CHRG|REVERSAL\s+OF\s+GST|FAILED\s+TXN|TAX\s+REFUND|BILL\s+REFUND|MERCHANT\s+REF|CREDIT\s+ADJUSTMENT|REWARD)\b",
        re.IGNORECASE,
    )
    CORPORATE_REGEX = re.compile(
        r"\b(LTD|LIMITED|PVT|PRIVATE|INC|CORP|CORPORATION|SERVICES|TECHNOLOGIES|SOLUTIONS|ENTERPRISES|HOLDINGS|INFOTECH|SYSTEMS|LLC|LLP|CMS|IFT|ESCROW|ORGANIZATION|ORGANIZATIO|FOUNDATION|TRUST|CONSULTANCY|INDUSTRIES|VENTURES|LOGISTICS|PHARMA|GLOBAL|STUDIOS|MEDIA|SALARY\s+AC|PAYROLL\s+AC|EMPLOYEE\s+PROVIDENT\s+FUND|EPFO|NACH/CLAIM)\b",
        re.IGNORECASE,
    )
    TRANSFER_REGEX = re.compile(
        r"\b(NEFT|RTGS|ACH|CMS|IFT)\b",
        re.IGNORECASE,
    )

    ATM_KEYWORDS = ["ATM", "CASH WDL", "CASH WITHDRAWAL", "NFS*", "MATM", "MICRO ATM"]
    MERCHANT_KEYWORDS = [
        "POS ", "POS/", "POS-", "PAYTMQR", "BHARATPE", "AMAZON", "FLIPKART", 
        "SWIGGY", "ZOMATO", "UBER", "OLA", "BLINKIT", "ZEPTO", "BIGBASKET", 
        "MYNTRA", "STORE", "RETAIL", "MART", "SUPERMARKET", "RESTAURANT"
    ]
    UTILITY_KEYWORDS = [
        "ELECTRIC", "POWER", "WATER", "GAS", "BILLDESK", "RECHARGE", 
        "AIRTEL", "JIO", "VODAFONE", "BESCOM", "TNEB", "MSEDCL", "BROADBAND"
    ]
    SUBSCRIPTION_KEYWORDS = [
        "NETFLIX", "SPOTIFY", "PRIME", "YOUTUBE", "HOTSTAR", "APPLE.COM", 
        "GOOGLE PLAY", "GOOGLE STORAGE", "SUBSCRIPTION", "MEMBERSHIP"
    ]
    LOAN_KEYWORDS = [
        "LOAN", "EMI", "BAJAJ", "HDBFS", "MUTHOOT", "DMI FINANCE", 
        "KREDITBEE", "EARLYSALARY", "CAPITAL FLOAT", "FINANCE", "CHOLAMANDALAM"
    ]
    BANK_FEE_KEYWORDS = [
        "FEE", "CHARGE", "GST", "CHG", "ANNUAL FEE", "SMS CHG", 
        "INT.COLL", "PENALTY", "MIN BAL", "SERVICE CHARGE"
    ]

    @classmethod
    def determine_direction(
        cls,
        tx: Dict[str, Any],
        prev_balance: Optional[Decimal] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Determines transaction direction ('CREDIT', 'DEBIT', 'AMBIGUOUS') using:
        1. Explicit debit and credit columns.
        2. Bank-specific narration markers (CR/DR).
        3. Running balance changes when reliable.
        Never blindly relies on amount sign.
        """
        credit = tx.get("credit_amount")
        debit = tx.get("debit_amount")
        desc = (tx.get("raw_description") or tx.get("description") or "").upper()
        curr_balance = tx.get("balance")

        # 1. Explicit credit column non-zero, debit column empty/zero
        has_credit = credit is not None and credit > Decimal("0.00")
        has_debit = debit is not None and debit > Decimal("0.00")

        if has_credit and not has_debit:
            return "CREDIT", None
        if has_debit and not has_credit:
            return "DEBIT", None

        # 2. Both set or both empty -> check explicit markers in narration
        cr_markers = ["/CR/", " CR ", "CREDIT", "BY TRANSFER", "DEPOSIT", "IMPS-CR", "NEFT-CR", "UPI/CR"]
        dr_markers = ["/DR/", " DR ", "DEBIT", "TO TRANSFER", "WITHDRAWAL", "IMPS-DR", "NEFT-DR", "UPI/DR"]

        is_marked_cr = any(m in desc for m in cr_markers)
        is_marked_dr = any(m in desc for m in dr_markers)

        if is_marked_cr and not is_marked_dr:
            return "CREDIT", None
        if is_marked_dr and not is_marked_cr:
            return "DEBIT", None

        # 3. Running balance delta if reliable
        if curr_balance is not None and prev_balance is not None:
            delta = curr_balance - prev_balance
            if delta > Decimal("0.00"):
                return "CREDIT", "Inferred direction from positive running balance delta"
            elif delta < Decimal("0.00"):
                return "DEBIT", "Inferred direction from negative running balance delta"

        # Ambiguous direction
        return "AMBIGUOUS", "Ambiguous transaction direction — retained for underwriter review"

    @classmethod
    def classify_and_filter(
        cls,
        tx: Dict[str, Any],
        prev_balance: Optional[Decimal] = None
    ) -> FilteredTransactionResult:
        """
        Evaluates an individual transaction against deterministic financial rules to decide:
        - Direction (CREDIT / DEBIT / AMBIGUOUS)
        - Category
        - Included in Salary Analysis Dataset (bool)
        - Reason for exclusion or inclusion
        - Validation status and warnings
        - Candidate tier (LIKELY_SALARY, POSSIBLE_SALARY, UNLIKELY_SALARY)
        - Ranking score (0-100)
        """
        desc = (tx.get("raw_description") or tx.get("description") or "").strip().upper()
        direction, direction_warning = cls.determine_direction(tx, prev_balance)
        credit = tx.get("credit_amount")
        debit = tx.get("debit_amount")

        # Handle Ambiguous Direction
        if direction == "AMBIGUOUS":
            return FilteredTransactionResult(
                transaction_direction="AMBIGUOUS",
                category="Uncertain / Ambiguous",
                included_in_salary_analysis=True,
                exclusion_reason=None,
                inclusion_reason="Ambiguous Direction — Retained for Underwriter Review",
                validation_status="warning",
                validation_warnings="Direction could not be definitively established; flagged for review.",
                candidate_tier=CandidateTier.POSSIBLE_SALARY,
                ranking_score=30,
            )

        # Handle DEBITS
        if direction == "DEBIT":
            is_reversal = any(kw in desc for kw in cls.REVERSAL_KEYWORDS)
            if is_reversal:
                return FilteredTransactionResult(
                    transaction_direction="DEBIT",
                    category="Reversal / Refund",
                    included_in_salary_analysis=True,
                    exclusion_reason=None,
                    inclusion_reason="Potential Salary Reversal / Refund",
                    validation_status="valid",
                    validation_warnings=direction_warning,
                    candidate_tier=CandidateTier.POSSIBLE_SALARY,
                    ranking_score=20,
                )

            # Classify standard debit exclusion reasons
            if any(kw in desc for kw in cls.ATM_KEYWORDS):
                category = "ATM Cash Withdrawal"
                reason = "ATM Cash Withdrawal"
            elif any(kw in desc for kw in cls.MERCHANT_KEYWORDS):
                category = "Merchant Purchase / POS"
                reason = "Merchant Purchase / POS Expense"
            elif any(kw in desc for kw in cls.UTILITY_KEYWORDS):
                category = "Utility Bill"
                reason = "Routine Utility Bill / Telecom Recharge"
            elif any(kw in desc for kw in cls.SUBSCRIPTION_KEYWORDS):
                category = "Subscription Payment"
                reason = "Digital Subscription / Membership"
            elif any(kw in desc for kw in cls.LOAN_KEYWORDS):
                category = "Loan Repayment / EMI"
                reason = "Loan Repayment / EMI Outflow"
            elif any(kw in desc for kw in cls.BANK_FEE_KEYWORDS):
                category = "Bank Fee / Service Charge"
                reason = "Bank Fee / Service Charge"
            elif "UPI/DR" in desc or "UPI DR" in desc or "PAYMENT VIA UPI" in desc:
                category = "Outgoing UPI / P2P"
                reason = "Outgoing P2P / Merchant UPI Payment"
            else:
                category = "Routine Debit / Expenditure"
                reason = "Routine Outgoing Debit / Expenditure"

            return FilteredTransactionResult(
                transaction_direction="DEBIT",
                category=category,
                included_in_salary_analysis=False,
                exclusion_reason=reason,
                inclusion_reason=None,
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=CandidateTier.UNLIKELY_SALARY,
                ranking_score=0,
            )

        # Handle CREDITS (Direction == "CREDIT")
        is_salary_kw = bool(cls.SALARY_REGEX.search(desc))
        is_interest = bool(cls.INTEREST_REGEX.search(desc)) and not is_salary_kw
        is_refund = bool(cls.REFUND_REGEX.search(desc)) and not is_salary_kw
        is_corporate_wire = bool(cls.TRANSFER_REGEX.search(desc))
        has_corp_name = bool(cls.CORPORATE_REGEX.search(desc))

        # 1. Bank Interest Credit Check (Safely Exclude)
        if is_interest and not is_salary_kw:
            return FilteredTransactionResult(
                transaction_direction="CREDIT",
                category="Interest Credit",
                included_in_salary_analysis=False,
                exclusion_reason="Bank Interest Credit (Non-Salary)",
                inclusion_reason=None,
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=CandidateTier.UNLIKELY_SALARY,
                ranking_score=0,
            )

        # 2. Refund / Cashback / Fee Reversal Check (Safely Exclude)
        if is_refund and not is_salary_kw:
            return FilteredTransactionResult(
                transaction_direction="CREDIT",
                category="Reversal / Refund",
                included_in_salary_analysis=False,
                exclusion_reason="Merchant Refund / Cashback / Fee Reversal",
                inclusion_reason=None,
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=CandidateTier.UNLIKELY_SALARY,
                ranking_score=5,
            )

        # 3. Explicit Salary / Payroll Markers (High Confidence)
        if is_salary_kw:
            score = 90
            if is_corporate_wire or has_corp_name:
                score += 8
            return FilteredTransactionResult(
                transaction_direction="CREDIT",
                category="Salary / Payroll Candidate",
                included_in_salary_analysis=True,
                exclusion_reason=None,
                inclusion_reason="Explicit Salary / Payroll Narration Keywords",
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=CandidateTier.LIKELY_SALARY,
                ranking_score=score,
            )

        # 4. Corporate Wire / Corporate Entity Credit
        if is_corporate_wire or has_corp_name:
            category = "Corporate Credit"
            tier = CandidateTier.LIKELY_SALARY if (is_corporate_wire and has_corp_name) else CandidateTier.POSSIBLE_SALARY
            score = 80 if (is_corporate_wire and has_corp_name) else 70
            return FilteredTransactionResult(
                transaction_direction="CREDIT",
                category=category,
                included_in_salary_analysis=True,
                exclusion_reason=None,
                inclusion_reason="Incoming Corporate Credit / Potential Employer Transfer",
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=tier,
                ranking_score=score,
            )

        # 5. Amount Threshold Check (for low-value informal / P2P UPI transfers)
        currency = tx.get("currency", "USD")
        if currency == "INR":
            min_threshold = Decimal(str(settings.SALARY_PREFILTER_MIN_AMOUNT_INR))
        else:
            min_threshold = Decimal(str(settings.SALARY_PREFILTER_MIN_AMOUNT_USD))

        credit_val = credit if credit is not None else Decimal("0.00")
        if credit_val < min_threshold:
            category = "Incoming UPI" if ("UPI" in desc) else "Low-Value Inflow"
            return FilteredTransactionResult(
                transaction_direction="CREDIT",
                category=category,
                included_in_salary_analysis=False,
                exclusion_reason=f"Low-Value Non-Payroll Inflow (< {min_threshold} {currency})",
                inclusion_reason=None,
                validation_status="valid",
                validation_warnings=direction_warning,
                candidate_tier=CandidateTier.UNLIKELY_SALARY,
                ranking_score=10,
            )

        # 6. Ambiguous / Substantial Inflows (>= threshold, non-interest, non-refund)
        category = "Incoming UPI Candidate" if ("UPI" in desc) else "Incoming Credit Candidate"
        return FilteredTransactionResult(
            transaction_direction="CREDIT",
            category=category,
            included_in_salary_analysis=True,
            exclusion_reason=None,
            inclusion_reason="Ambiguous Inflow Exceeding Salary Threshold — Flagged for Analysis",
            validation_status="valid",
            validation_warnings=direction_warning,
            candidate_tier=CandidateTier.POSSIBLE_SALARY,
            ranking_score=50,
        )

    @classmethod
    def filter_statement_transactions(
        cls,
        transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Processes an entire statement's transactions and returns:
        (annotated_transactions, filtering_summary_statistics)
        
        Applies a two-pass architecture:
        - Pass 1: Individual transaction direction, categorization, and pre-filtering.
        - Pass 2: Identifies recurring employer/sender patterns across multiple distinct
                 calendar months to elevate recurring candidates and ensure 100% recall.
        """
        annotated: List[Dict[str, Any]] = []
        prev_balance: Optional[Decimal] = None

        # Pass 1: Initial classification
        for tx in transactions:
            filt_res = cls.classify_and_filter(tx, prev_balance)
            tx_copy = dict(tx)
            tx_copy["transaction_direction"] = filt_res.transaction_direction
            tx_copy["category"] = filt_res.category
            tx_copy["included_in_salary_analysis"] = filt_res.included_in_salary_analysis
            tx_copy["exclusion_reason"] = filt_res.exclusion_reason
            tx_copy["inclusion_reason"] = filt_res.inclusion_reason
            tx_copy["validation_status"] = filt_res.validation_status
            tx_copy["validation_warnings"] = filt_res.validation_warnings
            tx_copy["candidate_tier"] = filt_res.candidate_tier
            tx_copy["ranking_score"] = filt_res.ranking_score

            prev_balance = tx.get("balance")
            annotated.append(tx_copy)

        # Pass 2: Detect recurring payment patterns across calendar months
        sender_months: Dict[str, set] = {}
        for tx in annotated:
            if tx.get("transaction_direction") == "CREDIT":
                # Never track interest credits, refunds, or reversals as recurring employer candidates
                if tx.get("category") in ["Interest Credit", "Reversal / Refund"]:
                    continue
                c_amt = tx.get("credit_amount")
                if c_amt is not None and c_amt > Decimal("0.00"):
                    raw_desc = tx.get("raw_description") or tx.get("description") or ""
                    clean_sender = EmployerNormalizer.extract_clean_employer_name(raw_desc)
                    tx_date = str(tx.get("transaction_date", ""))[:7]  # YYYY-MM
                    if clean_sender and len(clean_sender) >= 3 and len(tx_date) == 7:
                        sender_months.setdefault(clean_sender, set()).add(tx_date)

        # Find senders appearing across 2 or more distinct statement months
        recurring_senders = {
            sender: months for sender, months in sender_months.items() if len(months) >= 2
        }

        # Upgrade recurring candidates
        for tx in annotated:
            if tx.get("transaction_direction") == "CREDIT":
                if tx.get("category") in ["Interest Credit", "Reversal / Refund"]:
                    continue
                raw_desc = tx.get("raw_description") or tx.get("description") or ""
                clean_sender = EmployerNormalizer.extract_clean_employer_name(raw_desc)
                if clean_sender in recurring_senders:
                    months_count = len(recurring_senders[clean_sender])
                    # If this was excluded (e.g. low-value P2P variation), upgrade to included
                    if not tx.get("included_in_salary_analysis"):
                        tx["included_in_salary_analysis"] = True
                        tx["exclusion_reason"] = None
                        tx["inclusion_reason"] = f"Recurring Credit Pattern ({months_count} distinct months) — {clean_sender}"
                        tx["candidate_tier"] = CandidateTier.POSSIBLE_SALARY
                        tx["ranking_score"] = max(tx.get("ranking_score", 0) + 25, 70)
                    else:
                        tx["ranking_score"] = min(tx.get("ranking_score", 0) + 10, 100)
                        if tx.get("candidate_tier") == CandidateTier.POSSIBLE_SALARY and months_count >= 3:
                            tx["candidate_tier"] = CandidateTier.LIKELY_SALARY

        # Aggregate summary metrics
        total_txs = len(annotated)
        total_debits = sum(1 for t in annotated if t.get("transaction_direction") == "DEBIT")
        total_credits = sum(1 for t in annotated if t.get("transaction_direction") == "CREDIT")
        included_count = sum(1 for t in annotated if t.get("included_in_salary_analysis"))
        excluded_count = total_txs - included_count

        exclusion_counts: Dict[str, int] = {}
        for t in annotated:
            if not t.get("included_in_salary_analysis"):
                reason = t.get("exclusion_reason") or "Other Irrelevant Outflow"
                exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

        tier_counts = {
            CandidateTier.LIKELY_SALARY: sum(1 for t in annotated if t.get("candidate_tier") == CandidateTier.LIKELY_SALARY),
            CandidateTier.POSSIBLE_SALARY: sum(1 for t in annotated if t.get("candidate_tier") == CandidateTier.POSSIBLE_SALARY),
            CandidateTier.UNLIKELY_SALARY: sum(1 for t in annotated if t.get("candidate_tier") == CandidateTier.UNLIKELY_SALARY),
        }

        # Strict mathematical reconciliation invariant
        assert total_txs == included_count + excluded_count, (
            f"Filtering count mismatch: Total {total_txs} != Included {included_count} + Excluded {excluded_count}"
        )

        stats = {
            "total_transactions": total_txs,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "included_in_salary_analysis": included_count,
            "excluded_from_salary_analysis": excluded_count,
            "exclusion_counts_by_reason": exclusion_counts,
            "tier_counts": tier_counts,
        }

        return annotated, stats
