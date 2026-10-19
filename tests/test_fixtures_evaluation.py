"""
Evaluation tests verifying all 10 synthetic fixtures against expected financial outcomes
"""
import json
from decimal import Decimal
from pathlib import Path
import pytest

from app.services.document_processing.extractor import DocumentExtractor
from app.services.salary_detection.engine import FinancialValidationEngine

FIXTURES_DIR = Path("fixtures/synthetic_statements")
EXPECTED_DIR = Path("fixtures/expected_results")


def test_eval_01_clear_monthly_salary():
    res = json.loads((EXPECTED_DIR / "01_clear_monthly_salary.json").read_text())
    doc = DocumentExtractor.extract_document(str(FIXTURES_DIR / "01_clear_monthly_salary.pdf"))
    assert doc.is_scanned is False

    txs = [
        {"id": "1", "transaction_date": "2026-03-31", "raw_description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "credit_amount": Decimal("5250.00"), "debit_amount": None},
        {"id": "2", "transaction_date": "2026-04-30", "raw_description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "credit_amount": Decimal("5250.00"), "debit_amount": None},
        {"id": "3", "transaction_date": "2026-05-30", "raw_description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP", "credit_amount": Decimal("5250.00"), "debit_amount": None},
    ]
    fin = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=3)
    assert fin.status == res["expected_status"]
    assert len(fin.candidate_groups[0].months) == res["expected_months_count"]


def test_eval_06_multiple_employers():
    res = json.loads((EXPECTED_DIR / "06_multiple_employers.json").read_text())
    txs = [
        {"id": "1", "transaction_date": "2026-03-31", "raw_description": "ACH CREDIT ALPHA HOLDINGS SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        {"id": "2", "transaction_date": "2026-04-30", "raw_description": "ACH CREDIT ALPHA HOLDINGS SALARY", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        {"id": "3", "transaction_date": "2026-03-15", "raw_description": "DIR DEP BETA LOGISTICS PAYROLL", "credit_amount": Decimal("3500.00"), "debit_amount": None},
        {"id": "4", "transaction_date": "2026-04-15", "raw_description": "DIR DEP BETA LOGISTICS PAYROLL", "credit_amount": Decimal("3500.00"), "debit_amount": None},
    ]
    fin = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=2)
    assert fin.status == res["expected_status"]


def test_eval_07_missing_months():
    res = json.loads((EXPECTED_DIR / "07_missing_months.json").read_text())
    txs = [
        {"id": "1", "transaction_date": "2026-03-31", "raw_description": "ACH CREDIT DELTA CORP SALARY", "credit_amount": Decimal("4500.00"), "debit_amount": None},
        {"id": "2", "transaction_date": "2026-05-31", "raw_description": "ACH CREDIT DELTA CORP SALARY", "credit_amount": Decimal("4500.00"), "debit_amount": None},
    ]
    fin = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=3)
    assert fin.status == res["expected_status"]
    assert fin.candidate_groups[0].missing_months == res["expected_missing_months"]


def test_eval_08_reversed_transactions():
    res = json.loads((EXPECTED_DIR / "08_reversed_transactions.json").read_text())
    txs = [
        {"id": "1", "transaction_date": "2026-03-31", "raw_description": "ACH CREDIT REGULAR SALARY CORP", "credit_amount": Decimal("4000.00"), "debit_amount": None},
        {"id": "2", "transaction_date": "2026-04-10", "raw_description": "ERRONEOUS SALARY DEPOSIT", "credit_amount": Decimal("2000.00"), "debit_amount": None},
        {"id": "3", "transaction_date": "2026-04-12", "raw_description": "REVERSAL ERRONEOUS SALARY DEPOSIT", "credit_amount": None, "debit_amount": Decimal("2000.00")},
        {"id": "4", "transaction_date": "2026-04-30", "raw_description": "ACH CREDIT REGULAR SALARY CORP", "credit_amount": Decimal("4000.00"), "debit_amount": None},
    ]
    fin = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=2)
    assert len(fin.reversals_detected) == res["reversals_count"]
    assert fin.status == res["expected_status"]


def test_eval_09_scanned_unreadable():
    res = json.loads((EXPECTED_DIR / "09_unreadable_scanned.json").read_text())
    doc = DocumentExtractor.extract_document(str(FIXTURES_DIR / "09_unreadable_scanned.pdf"))
    assert doc.is_scanned == res["expected_is_scanned"]


def test_eval_10_insufficient_evidence():
    res = json.loads((EXPECTED_DIR / "10_insufficient_evidence.json").read_text())
    txs = [
        {"id": "1", "transaction_date": "2026-03-05", "raw_description": "COFFEE SHOP", "credit_amount": None, "debit_amount": Decimal("4.50")},
        {"id": "2", "transaction_date": "2026-03-20", "raw_description": "ATM CASH DEPOSIT", "credit_amount": Decimal("50.00"), "debit_amount": None},
    ]
    fin = FinancialValidationEngine.analyze_transactions(txs, duration_months_hint=2)
    assert fin.status == res["expected_status"]
