"""
Comprehensive unit tests for Python Financial Validation Engine
"""
import uuid
from decimal import Decimal
from datetime import date
import pytest

from app.services.salary_detection.engine import FinancialValidationEngine
from app.services.salary_detection.normalizer import EmployerNormalizer


def test_employer_normalization():
    assert EmployerNormalizer.extract_clean_employer_name("ACH CREDIT ACME TECH CORP SALARY DIR DEP") == "ACME TECH CORP"
    assert EmployerNormalizer.extract_clean_employer_name("DIRECT DEP GOOGLE LLC PAYROLL PPD ID: 994") == "GOOGLE LLC"
    assert EmployerNormalizer.are_employers_similar("ACME TECH CORP", "ACME TECH CORPORATION") is True
    assert EmployerNormalizer.are_employers_similar("GOOGLE LLC", "AMAZON SERVICES") is False


def test_clear_monthly_salary():
    txs = [
        {"id": uuid.uuid4(), "transaction_date": "2026-03-31", "raw_description": "ACH CREDIT ACME TECH SALARY", "credit_amount": Decimal("5000.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-04-30", "raw_description": "ACH CREDIT ACME TECH SALARY", "credit_amount": Decimal("5000.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-05-29", "raw_description": "ACH CREDIT ACME TECH SALARY", "credit_amount": Decimal("5000.00"), "debit_amount": None},
    ]
    result = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=3)
    assert result.has_salary_candidates is True
    assert result.status == "likely_salary"
    assert len(result.candidate_groups) == 1

    group = result.candidate_groups[0]
    assert group.average_amount == Decimal("5000.00")
    assert group.median_amount == Decimal("5000.00")
    assert group.min_amount == Decimal("5000.00")
    assert group.max_amount == Decimal("5000.00")
    assert group.amount_variation_pct == Decimal("0.00")
    assert len(group.missing_months) == 0
    assert group.is_primary is True


def test_salary_variation_and_different_dates():
    # 28th, 30th, 27th with amounts varying slightly
    txs = [
        {"id": uuid.uuid4(), "transaction_date": "2026-01-28", "raw_description": "DIR DEP TECHCORP INC SALARY", "credit_amount": Decimal("4800.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-02-27", "raw_description": "DIR DEP TECHCORP INC SALARY", "credit_amount": Decimal("5000.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-03-30", "raw_description": "DIR DEP TECHCORP INC SALARY", "credit_amount": Decimal("5200.00"), "debit_amount": None},
    ]
    result = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=3)
    assert result.status == "likely_salary"
    group = result.candidate_groups[0]
    assert group.average_amount == Decimal("5000.00")
    assert group.median_amount == Decimal("5000.00")
    assert group.min_amount == Decimal("4800.00")
    assert group.max_amount == Decimal("5200.00")
    assert group.amount_variation_pct == Decimal("8.00")  # (400 / 5000) * 100 = 8.00%


def test_missing_month_detection():
    # March and May present, April missing
    txs = [
        {"id": uuid.uuid4(), "transaction_date": "2026-03-31", "raw_description": "ACME SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-05-31", "raw_description": "ACME SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
    ]
    result = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=3)
    assert result.status == "possible_salary"
    group = result.candidate_groups[0]
    assert "2026-04" in group.missing_months


def test_duplicate_and_reversal_detection():
    tx_id_1 = uuid.uuid4()
    tx_id_dup = uuid.uuid4()
    tx_id_cred = uuid.uuid4()
    tx_id_rev = uuid.uuid4()

    txs = [
        # Regular salary
        {"id": tx_id_1, "transaction_date": "2026-03-31", "raw_description": "CORP SALARY", "credit_amount": Decimal("3000.00"), "debit_amount": None},
        # Duplicate of above
        {"id": tx_id_dup, "transaction_date": "2026-03-31", "raw_description": "CORP SALARY", "credit_amount": Decimal("3000.00"), "debit_amount": None},
        # Reversed transaction
        {"id": tx_id_cred, "transaction_date": "2026-04-10", "raw_description": "ERRONEOUS CREDIT", "credit_amount": Decimal("1500.00"), "debit_amount": None},
        {"id": tx_id_rev, "transaction_date": "2026-04-12", "raw_description": "REVERSAL ERRONEOUS CREDIT", "credit_amount": None, "debit_amount": Decimal("1500.00")},
    ]
    result = FinancialValidationEngine.analyze_transactions(txs)
    assert str(tx_id_dup) in result.duplicates_detected
    assert str(tx_id_cred) in result.reversals_detected


def test_multiple_competing_employers():
    txs = [
        # Employer A
        {"id": uuid.uuid4(), "transaction_date": "2026-01-31", "raw_description": "ALPHA CORP SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-02-28", "raw_description": "ALPHA CORP SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        # Employer B
        {"id": uuid.uuid4(), "transaction_date": "2026-01-15", "raw_description": "BETA LOGISTICS PAYROLL", "credit_amount": Decimal("3500.00"), "debit_amount": None},
        {"id": uuid.uuid4(), "transaction_date": "2026-02-15", "raw_description": "BETA LOGISTICS PAYROLL", "credit_amount": Decimal("3500.00"), "debit_amount": None},
    ]
    result = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=2)
    assert result.status == "multiple_salary_candidates"
    assert len(result.candidate_groups) >= 2
