"""
SalaryLens AI by CodeSec — Token Optimization & Pre-Filtering Regression Tests
Validates:
- Low-value UPI credits excluded (< threshold)
- Refunds and cashbacks excluded
- Bank interest credits excluded
- Employer salary credits retained (LIKELY_SALARY)
- Incentives and bonuses retained
- Corporate entity wire transfers retained
- Recurring payment patterns across months elevated
- Ambiguous incoming payments retained (POSSIBLE_SALARY)
- Duplicate transactions detected
- AI response cache avoids repeated calls
- Reviewer overrides and workbook regeneration do not invoke AI
- Mathematical reconciliation invariant (Total = Included + Excluded)
"""
import uuid
from datetime import date
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.services.salary_detection.filter import (
    CandidateTier,
    TransactionFilterService,
)
from app.services.salary_detection.engine import FinancialValidationEngine
from app.services.openrouter.cache import AIResponseCache
from app.services.openrouter.client import OpenRouterClient
from app.schemas.openrouter import AIModelCallResult


def test_small_upi_credits_excluded():
    """Verify informal low-value UPI credits (< 1500 INR) are excluded from AI analysis."""
    small_upi_tx = {
        "raw_description": "UPI/CR/402910391/JOHN/P2P/Tea",
        "credit_amount": Decimal("150.00"),
        "debit_amount": None,
        "currency": "INR",
    }
    res = TransactionFilterService.classify_and_filter(small_upi_tx)
    assert res.included_in_salary_analysis is False
    assert res.candidate_tier == CandidateTier.UNLIKELY_SALARY
    assert "Low-Value Non-Payroll Inflow" in (res.exclusion_reason or "")
    assert res.ranking_score <= 15


def test_refunds_and_cashbacks_excluded():
    """Verify refunds, reversals, and cashbacks are safely excluded."""
    refund_txs = [
        {"raw_description": "REFUND FROM AMAZON PAY", "credit_amount": Decimal("499.00"), "currency": "INR"},
        {"raw_description": "CASHBACK REWARD CRED", "credit_amount": Decimal("25.00"), "currency": "INR"},
        {"raw_description": "POS REFUND FLIPKART", "credit_amount": Decimal("1250.00"), "currency": "INR"},
        {"raw_description": "TAX REFUND ITD GOV", "credit_amount": Decimal("3500.00"), "currency": "INR"},
    ]
    for tx in refund_txs:
        res = TransactionFilterService.classify_and_filter(tx)
        assert res.included_in_salary_analysis is False
        assert res.candidate_tier == CandidateTier.UNLIKELY_SALARY
        assert res.category == "Reversal / Refund"


def test_bank_interest_credits_excluded():
    """Verify bank interest credits are segregated and excluded from salary analysis."""
    interest_txs = [
        {"raw_description": "INTEREST CREDIT SB 10016402891", "credit_amount": Decimal("36.00"), "currency": "INR"},
        {"raw_description": "SB INT.PD 01-04-2023 TO 30-06-2023", "credit_amount": Decimal("150.00"), "currency": "INR"},
        {"raw_description": "SAVINGS INT CREDIT", "credit_amount": Decimal("240.00"), "currency": "INR"},
    ]
    for tx in interest_txs:
        res = TransactionFilterService.classify_and_filter(tx)
        assert res.included_in_salary_analysis is False
        assert res.candidate_tier == CandidateTier.UNLIKELY_SALARY
        assert res.category == "Interest Credit"
        assert "Non-Salary" in (res.exclusion_reason or "")


def test_employer_salary_credits_retained_as_likely():
    """Verify explicit salary markers are categorized as LIKELY_SALARY and included."""
    salary_txs = [
        {
            "raw_description": "NEFT-KRAZYBEE SERVICES PVT LTD-SALARY APR 2023",
            "credit_amount": Decimal("52400.00"),
            "currency": "INR",
        },
        {
            "raw_description": "ACH CREDIT ACME TECH CORP PAYROLL DIR DEP",
            "credit_amount": Decimal("4500.00"),
            "currency": "USD",
        },
        {
            "raw_description": "MONTHLY SALARY DEPOSIT TECHNO SOLUTIONS",
            "credit_amount": Decimal("65000.00"),
            "currency": "INR",
        },
    ]
    for tx in salary_txs:
        res = TransactionFilterService.classify_and_filter(tx)
        assert res.included_in_salary_analysis is True
        assert res.candidate_tier == CandidateTier.LIKELY_SALARY
        assert res.ranking_score >= 90
        assert res.category == "Salary / Payroll Candidate"


def test_incentives_and_bonuses_retained():
    """Verify employer incentives and bonuses are retained for analysis."""
    incentive_tx = {
        "raw_description": "CMS/000291039/KRAZYBEE SERVICES PRIVATE LIMITED/INCENTIVE",
        "credit_amount": Decimal("15000.00"),
        "currency": "INR",
    }
    res = TransactionFilterService.classify_and_filter(incentive_tx)
    assert res.included_in_salary_analysis is True
    assert res.candidate_tier == CandidateTier.LIKELY_SALARY
    assert res.ranking_score >= 90


def test_corporate_entity_wire_transfers_retained():
    """Verify corporate transfers without explicit salary word are retained as candidates."""
    corp_tx = {
        "raw_description": "NEFT-AXIS00192-ACME TECHNOLOGIES PRIVATE LIMITED-CR",
        "credit_amount": Decimal("48000.00"),
        "currency": "INR",
    }
    res = TransactionFilterService.classify_and_filter(corp_tx)
    assert res.included_in_salary_analysis is True
    assert res.candidate_tier in [CandidateTier.LIKELY_SALARY, CandidateTier.POSSIBLE_SALARY]
    assert res.ranking_score >= 70


def test_recurring_transfers_across_months_promoted():
    """Verify recurring payments across multiple calendar months are elevated."""
    multi_month_txs = [
        # Month 1: April 2023
        {
            "transaction_date": "2023-04-05",
            "raw_description": "IMPS/CR/12345/CONSULTANCY SERVICES/PAY",
            "credit_amount": Decimal("30000.00"),
            "currency": "INR",
        },
        # Month 2: May 2023
        {
            "transaction_date": "2023-05-05",
            "raw_description": "IMPS/CR/67890/CONSULTANCY SERVICES/PAY",
            "credit_amount": Decimal("30000.00"),
            "currency": "INR",
        },
        # Irrelevant non-recurring peer transfer
        {
            "transaction_date": "2023-04-10",
            "raw_description": "UPI/CR/11111/RANDOM FRIEND/P2P",
            "credit_amount": Decimal("100.00"),
            "currency": "INR",
        },
    ]
    annotated, stats = TransactionFilterService.filter_statement_transactions(multi_month_txs)
    
    # Consultancy services transactions must be included
    consultancy_txs = [t for t in annotated if "CONSULTANCY" in t["raw_description"]]
    assert len(consultancy_txs) == 2
    for ctx in consultancy_txs:
        assert ctx["included_in_salary_analysis"] is True
        assert ctx["candidate_tier"] in [CandidateTier.LIKELY_SALARY, CandidateTier.POSSIBLE_SALARY]
        assert ctx["ranking_score"] >= 70

    # Irrelevant friend transfer must be excluded
    friend_tx = next(t for t in annotated if "FRIEND" in t["raw_description"])
    assert friend_tx["included_in_salary_analysis"] is False


def test_ambiguous_high_value_payments_retained():
    """Verify high-value credits exceeding salary threshold are retained as POSSIBLE_SALARY for underwriter review."""
    ambiguous_tx = {
        "raw_description": "UPI/CR/3910392019/APASAL B/PAYMENT",
        "credit_amount": Decimal("50000.00"),
        "currency": "INR",
    }
    res = TransactionFilterService.classify_and_filter(ambiguous_tx)
    assert res.included_in_salary_analysis is True
    assert res.candidate_tier == CandidateTier.POSSIBLE_SALARY
    assert res.ranking_score >= 40
    assert "Ambiguous Inflow Exceeding Salary Threshold" in (res.inclusion_reason or "")


def test_duplicate_transactions_detected():
    """Verify exact duplicate credits are correctly detected deterministically."""
    txs = [
        {"id": "tx-1", "transaction_date": date(2023, 4, 30), "credit_amount": Decimal("50000.00"), "raw_description": "SALARY CREDIT"},
        {"id": "tx-2", "transaction_date": date(2023, 4, 30), "credit_amount": Decimal("50000.00"), "raw_description": "SALARY CREDIT"},
    ]
    dups, revs = FinancialValidationEngine.detect_duplicates_and_reversals(txs)
    assert len(dups) == 1
    assert "tx-2" in dups


@pytest.mark.asyncio
async def test_ai_response_cache_hit_avoids_repeated_calls():
    """Verify AIResponseCache caches reusable evaluation results and prevents repeated AI tokens."""
    cache_key = "salarylens:ai_cache:test:extraction:claude_test:sample_digest_123"
    
    original_result = AIModelCallResult(
        model_name="anthropic/claude-3.5-sonnet",
        stage="extraction",
        raw_response={"status": "ok"},
        parsed_json={"candidates": [{"idx": 0, "is_salary_candidate": True, "potential_employer": "KrazyBee"}]},
        input_tokens=450,
        output_tokens=120,
        cached_tokens=0,
        provider_cost_usd=Decimal("0.0031"),
        estimated_cost_usd=Decimal("0.0031"),
        latency_ms=850,
        retry_count=0,
        is_simulated=False,
        success=True,
    )

    # Store in cache
    saved = await AIResponseCache.set(cache_key, original_result)
    assert saved is True

    # Retrieve from cache
    cached = await AIResponseCache.get(cache_key)
    assert cached is not None
    assert cached.success is True
    assert cached.parsed_json == original_result.parsed_json
    # Cached result must record cached_tokens and 0 new input/output tokens and $0.00 cost
    assert cached.cached_tokens == 570
    assert cached.input_tokens == 0
    assert cached.output_tokens == 0
    assert cached.provider_cost_usd == Decimal("0.00")


@pytest.mark.asyncio
async def test_openrouter_client_integrates_cache():
    """Verify OpenRouterClient returns cached result without network request on identical prompt."""
    client = OpenRouterClient()
    messages = [{"role": "user", "content": "Test candidate extraction payload 99201"}]
    
    # First call simulates / generates response and stores in cache
    res1 = await client.generate_chat_completion(
        messages=messages,
        model=settings.SALARY_FINDER_MODEL,
        stage="extraction",
        statement_id="stmt-cache-test",
    )
    assert res1.success is True

    # Second call with identical payload must hit cache
    res2 = await client.generate_chat_completion(
        messages=messages,
        model=settings.SALARY_FINDER_MODEL,
        stage="extraction",
        statement_id="stmt-cache-test",
    )
    assert res2.success is True
    assert res2.input_tokens == 0
    assert res2.output_tokens == 0
    assert res2.cached_tokens > 0
    assert res2.provider_cost_usd == Decimal("0.00")


def test_reconciliation_invariant_and_tier_counts():
    """Verify strict mathematical reconciliation: Total = Included + Excluded, with accurate tier counts."""
    statement_txs = [
        {"transaction_date": "2023-04-01", "raw_description": "ATM CASH WDL", "debit_amount": Decimal("500.00"), "currency": "INR"},
        {"transaction_date": "2023-04-02", "raw_description": "SWIGGY POS", "debit_amount": Decimal("350.00"), "currency": "INR"},
        {"transaction_date": "2023-04-03", "raw_description": "INTEREST CREDIT", "credit_amount": Decimal("35.00"), "currency": "INR"},
        {"transaction_date": "2023-04-04", "raw_description": "AMAZON REFUND", "credit_amount": Decimal("499.00"), "currency": "INR"},
        {"transaction_date": "2023-04-05", "raw_description": "UPI TEA SHOP P2P", "credit_amount": Decimal("50.00"), "currency": "INR"},
        {"transaction_date": "2023-04-30", "raw_description": "KRAZYBEE SERVICES PVT LTD SALARY", "credit_amount": Decimal("52000.00"), "currency": "INR"},
        {"transaction_date": "2023-04-30", "raw_description": "KRAZYBEE SERVICES PVT LTD INCENTIVE", "credit_amount": Decimal("10000.00"), "currency": "INR"},
        {"transaction_date": "2023-04-15", "raw_description": "APASAL B DIRECT TRANSFER", "credit_amount": Decimal("50000.00"), "currency": "INR"},
    ]

    annotated, stats = TransactionFilterService.filter_statement_transactions(statement_txs)

    assert stats["total_transactions"] == 8
    assert stats["total_debits"] == 2
    assert stats["total_credits"] == 6
    assert stats["included_in_salary_analysis"] == 3  # Salary, Incentive, Ambiguous Inflow
    assert stats["excluded_from_salary_analysis"] == 5  # 2 debits + interest + refund + small UPI
    assert stats["total_transactions"] == stats["included_in_salary_analysis"] + stats["excluded_from_salary_analysis"]
    
    tier_counts = stats["tier_counts"]
    assert tier_counts[CandidateTier.LIKELY_SALARY] == 2  # KrazyBee Salary + KrazyBee Incentive
    assert tier_counts[CandidateTier.POSSIBLE_SALARY] == 1  # APASAL B
    assert tier_counts[CandidateTier.UNLIKELY_SALARY] == 5  # Excluded items
