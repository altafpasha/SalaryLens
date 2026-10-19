"""
SalaryLens AI by CodeSec — Unit Tests for Transaction Filtering and Direction Safeguards
"""
import pytest
from decimal import Decimal
from app.services.salary_detection.filter import (
    TransactionFilterService,
    sanitize_excel_formula,
)


def test_sanitize_excel_formula_injection():
    # Dangerous formula characters must be prefixed with an apostrophe
    assert sanitize_excel_formula("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_excel_formula("+100*20") == "'+100*20"
    assert sanitize_excel_formula("-50+2") == "'-50+2"
    assert sanitize_excel_formula("@HYPERLINK('http://malicious.com')") == "'@HYPERLINK('http://malicious.com')"
    assert sanitize_excel_formula("\tcmd") == "'\tcmd"

    # Harmless values should remain untouched
    assert sanitize_excel_formula("Regular Narration") == "Regular Narration"
    assert sanitize_excel_formula("KRAZYBEE SERVICES LTD") == "KRAZYBEE SERVICES LTD"
    assert sanitize_excel_formula(100.50) == 100.50
    assert sanitize_excel_formula(Decimal("34500.00")) == Decimal("34500.00")
    assert sanitize_excel_formula(None) == ""


def test_direction_detection_explicit_columns():
    # Explicit credit column
    cr_tx = {"credit_amount": Decimal("5000.00"), "debit_amount": None, "raw_description": "ACH DEPOSIT"}
    direction, _ = TransactionFilterService.determine_direction(cr_tx)
    assert direction == "CREDIT"

    # Explicit debit column
    dr_tx = {"credit_amount": None, "debit_amount": Decimal("150.00"), "raw_description": "GROCERY STORE"}
    direction, _ = TransactionFilterService.determine_direction(dr_tx)
    assert direction == "DEBIT"


def test_direction_detection_narration_markers():
    # Both amounts empty, but narration has explicit credit marker
    tx = {"credit_amount": None, "debit_amount": None, "raw_description": "UPI/CR/12345/JOHN/YESB/Payment"}
    direction, _ = TransactionFilterService.determine_direction(tx)
    assert direction == "CREDIT"

    # Narration has explicit debit marker
    tx_dr = {"credit_amount": None, "debit_amount": None, "raw_description": "UPI/DR/67890/STORE/Payment"}
    direction, _ = TransactionFilterService.determine_direction(tx_dr)
    assert direction == "DEBIT"


def test_direction_detection_balance_delta():
    # Inferred from running balance delta
    tx_up = {"credit_amount": None, "debit_amount": None, "balance": Decimal("5000.00"), "raw_description": "TRANSFER"}
    direction, reason = TransactionFilterService.determine_direction(tx_up, prev_balance=Decimal("4000.00"))
    assert direction == "CREDIT"
    assert "positive running balance delta" in reason

    tx_down = {"credit_amount": None, "debit_amount": None, "balance": Decimal("3500.00"), "raw_description": "TRANSFER"}
    direction, reason = TransactionFilterService.determine_direction(tx_down, prev_balance=Decimal("4000.00"))
    assert direction == "DEBIT"
    assert "negative running balance delta" in reason


def test_direction_detection_ambiguous_triggers_review():
    tx = {"credit_amount": None, "debit_amount": None, "balance": None, "raw_description": "UNKNOWN CODE 9948"}
    filt_res = TransactionFilterService.classify_and_filter(tx)
    assert filt_res.transaction_direction == "AMBIGUOUS"
    assert filt_res.included_in_salary_analysis is True
    assert "Ambiguous Direction" in filt_res.inclusion_reason
    assert filt_res.validation_status == "warning"


def test_debit_exclusion_rules():
    # ATM withdrawal
    atm_tx = {"debit_amount": Decimal("500.00"), "credit_amount": None, "raw_description": "ATM CASH WDL #402"}
    res = TransactionFilterService.classify_and_filter(atm_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "ATM Cash Withdrawal"

    # Merchant purchase
    pos_tx = {"debit_amount": Decimal("84.20"), "credit_amount": None, "raw_description": "POS SWIGGY ORDER 492"}
    res = TransactionFilterService.classify_and_filter(pos_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "Merchant Purchase / POS"

    # Utility bill
    util_tx = {"debit_amount": Decimal("110.50"), "credit_amount": None, "raw_description": "ELECTRIC UTILITY CO BILL"}
    res = TransactionFilterService.classify_and_filter(util_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "Utility Bill"

    # Subscription
    sub_tx = {"debit_amount": Decimal("15.99"), "credit_amount": None, "raw_description": "NETFLIX.COM SUBSCRIPTION"}
    res = TransactionFilterService.classify_and_filter(sub_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "Subscription Payment"

    # Loan repayment
    loan_tx = {"debit_amount": Decimal("12000.00"), "credit_amount": None, "raw_description": "BAJAJ AUTO FINANCE EMI"}
    res = TransactionFilterService.classify_and_filter(loan_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "Loan Repayment / EMI"

    # Bank fee
    fee_tx = {"debit_amount": Decimal("25.00"), "credit_amount": None, "raw_description": "ANNUAL SMS ALERT CHARGE"}
    res = TransactionFilterService.classify_and_filter(fee_tx)
    assert res.included_in_salary_analysis is False
    assert res.category == "Bank Fee / Service Charge"


def test_reversal_debit_is_preserved_for_analysis():
    # A debit with reversal keywords must be preserved because it might reverse a salary credit
    rev_tx = {"debit_amount": Decimal("34000.00"), "credit_amount": None, "raw_description": "SALARY REVERSAL RETURNED UNCLAIMED"}
    res = TransactionFilterService.classify_and_filter(rev_tx)
    assert res.included_in_salary_analysis is True
    assert res.category == "Reversal / Refund"
    assert "Potential Salary Reversal" in res.inclusion_reason


def test_salary_credit_is_preserved():
    # Explicit salary keyword
    sal_tx = {"credit_amount": Decimal("5250.00"), "debit_amount": None, "raw_description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP"}
    res = TransactionFilterService.classify_and_filter(sal_tx)
    assert res.included_in_salary_analysis is True
    assert res.category == "Salary / Payroll Candidate"

    # Credit without explicit salary keyword (e.g. corporate wire or generic credit)
    corp_tx = {"credit_amount": Decimal("34641.00"), "debit_amount": None, "raw_description": "NEFT YESIG62230166908 KRAZYBEE SERVICES LTD"}
    res = TransactionFilterService.classify_and_filter(corp_tx)
    assert res.included_in_salary_analysis is True
    assert res.category == "Corporate Credit"


def test_filter_statement_transactions_reconciliation_invariant():
    tx_list = [
        {"id": "1", "credit_amount": Decimal("5000.00"), "debit_amount": None, "raw_description": "SALARY CREDIT"},
        {"id": "2", "credit_amount": None, "debit_amount": Decimal("100.00"), "raw_description": "ATM CASH WDL"},
        {"id": "3", "credit_amount": None, "debit_amount": Decimal("50.00"), "raw_description": "POS SWIGGY"},
        {"id": "4", "credit_amount": None, "debit_amount": Decimal("12.00"), "raw_description": "NETFLIX"},
        {"id": "5", "credit_amount": Decimal("3000.00"), "debit_amount": None, "raw_description": "NEFT CORP TRANSFER"},
        {"id": "6", "credit_amount": None, "debit_amount": Decimal("2000.00"), "raw_description": "REVERSAL RETURN REFUND"},
    ]

    annotated, stats = TransactionFilterService.filter_statement_transactions(tx_list)

    assert stats["total_transactions"] == 6
    assert stats["total_credits"] == 2
    assert stats["total_debits"] == 4
    # Included: Salary Credit, Neft Corp Transfer, and Reversal Debit = 3
    assert stats["included_in_salary_analysis"] == 3
    # Excluded: ATM, POS, Netflix = 3
    assert stats["excluded_from_salary_analysis"] == 3
    # Invariant holds
    assert stats["total_transactions"] == stats["included_in_salary_analysis"] + stats["excluded_from_salary_analysis"]
