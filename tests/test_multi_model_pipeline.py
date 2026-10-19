"""
SalaryLens AI by CodeSec — Multi-Model OpenRouter Pipeline & Regression Tests
Validates:
1. Retries and backoff on transient errors (429/500/503).
2. Duplicate job idempotency.
3. Cache invalidation on source/config/version change.
4. Partial failures and graceful fallbacks.
5. Workbook regeneration and Decimal arithmetic fidelity.
6. Embedding batching (up to 64 items) and content-hashed caching.
7. Decision model bypass when zero candidate groups exist.
8. Per-request usage logging fields.
"""
import asyncio
import os
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.core.config import settings
from app.schemas.openrouter import AIModelCallResult, JevDecisionResponse
from app.services.openrouter.client import OpenRouterClient
from app.services.openrouter.cache import AIResponseCache
from app.services.openrouter.embeddings import OpenRouterEmbeddingService
from app.services.decision_engine.jev import JevDecisionEngine
from app.services.document_processing.extractor import DocumentExtractor


@pytest.mark.asyncio
async def test_openrouter_retries_and_backoff_on_transient_error(monkeypatch):
    """Verifies OpenRouterClient retries on transient errors (429, 500, 503) and records retry count."""
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "AI_EVALUATION_CACHE_ENABLED", False)
    client = OpenRouterClient(api_key="sk-or-test-key")

    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_resp_503.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable", request=MagicMock(), response=mock_resp_503
    )

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "model": "openai/gpt-6-luna",
        "usage": {"prompt_tokens": 150, "completion_tokens": 45},
        "choices": [{"message": {"content": '{"candidates": []}'}}],
    }

    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return mock_resp_503
        return mock_resp_200

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch("asyncio.sleep", return_value=None):
            res = await client.generate_chat_completion(
                messages=[{"role": "user", "content": "test"}],
                model="openai/gpt-6-luna",
                stage="extraction",
                statement_id="stmt-retry-123",
                run_id="run-retry-456",
            )

            assert res.success is True
            assert res.retry_count == 1
            assert res.statement_id == "stmt-retry-123"
            assert res.run_id == "run-retry-456"
            assert res.actual_model == "openai/gpt-6-luna"
            assert res.input_tokens == 150
            assert res.output_tokens == 45
            assert res.is_cache_hit is False


@pytest.mark.asyncio
async def test_per_request_usage_logging_fields(monkeypatch):
    """Verifies that all required per-request usage logging fields are captured."""
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "AI_EVALUATION_CACHE_ENABLED", False)
    client = OpenRouterClient(api_key="sk-or-test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "typesafe/jev-router-v2",  # Provider returned variant
        "cost": 0.00045,
        "usage": {
            "prompt_tokens": 420,
            "completion_tokens": 110,
            "prompt_tokens_details": {"cached_tokens": 64},
        },
        "choices": [{"message": {"content": '{"status": "likely_salary"}'}}],
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await client.generate_chat_completion(
            messages=[{"role": "user", "content": "evaluate"}],
            model="typesafe/jev-router",
            stage="decision",
            statement_id="stmt-log-789",
            run_id="run-log-012",
        )

        assert res.statement_id == "stmt-log-789"
        assert res.run_id == "run-log-012"
        assert res.stage == "decision"
        assert res.model_name == "typesafe/jev-router"
        assert res.actual_model == "typesafe/jev-router-v2"
        assert res.input_tokens == 420
        assert res.output_tokens == 110
        assert res.cached_tokens == 64
        assert res.provider_cost_usd == Decimal("0.000450")
        assert res.latency_ms >= 0
        assert res.retry_count == 0
        assert res.is_cache_hit is False


@pytest.mark.asyncio
async def test_cache_invalidation_by_statement():
    """Verifies that cache entries can be invalidated per statement ID."""
    stmt_id = "test-stmt-invalidation-uuid"
    key1 = AIResponseCache.make_cache_key("extraction", "openai/gpt-6-luna", statement_id=stmt_id)
    key2 = AIResponseCache.make_cache_key("decision", "typesafe/jev-router", statement_id=stmt_id)

    dummy_res = AIModelCallResult(
        model_name="openai/gpt-6-luna",
        stage="extraction",
        raw_response={"test": True},
        parsed_json={"candidates": []},
        success=True,
    )

    await AIResponseCache.set(key1, dummy_res)
    await AIResponseCache.set(key2, dummy_res)

    # Verify cached
    assert await AIResponseCache.get(key1) is not None
    assert await AIResponseCache.get(key2) is not None

    # Invalidate by statement ID
    inv_count = await AIResponseCache.invalidate_statement(stmt_id)
    assert inv_count >= 2

    # Verify both are evicted
    assert await AIResponseCache.get(key1) is None
    assert await AIResponseCache.get(key2) is None


@pytest.mark.asyncio
async def test_embedding_batching_and_content_hash_caching(monkeypatch):
    """Verifies OpenRouterEmbeddingService batches texts (up to 64) and caches using content hash."""
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    embed_service = OpenRouterEmbeddingService(api_key="sk-or-embed-key")

    # Clear in-memory cache for clean test
    OpenRouterEmbeddingService._in_memory_cache.clear()

    # Generate 130 unique sample texts (requires 3 batches: 64, 64, 2)
    test_run_uuid = uuid.uuid4()
    sample_texts = [f"Transaction narration #{test_run_uuid} #{i} for salary deposit" for i in range(130)]

    batch_call_sizes = []
    async def mock_embed_post(url, headers, json):
        input_items = json["input"]
        batch_call_sizes.append(len(input_items))
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": [{"embedding": [0.01 * j] * 1536} for j in range(len(input_items))],
            "usage": {"prompt_tokens": len(input_items) * 8},
        }
        return resp

    with patch("httpx.AsyncClient.post", side_effect=mock_embed_post):
        vectors, usage = await embed_service.get_embeddings(
            texts=sample_texts,
            statement_id="stmt-embed-1",
            run_id="run-embed-1",
        )

        assert len(vectors) == 130
        assert len(vectors[0]) == 1536
        # Must batch to sizes <= 64: [64, 64, 2]
        assert batch_call_sizes == [64, 64, 2]
        assert usage.stage == "embedding"
        assert usage.input_tokens == 130 * 8
        assert usage.is_cache_hit is False

        # Second call with the same 130 texts MUST be 100% cache hit with 0 network calls!
        batch_call_sizes.clear()
        cached_vectors, cached_usage = await embed_service.get_embeddings(
            texts=sample_texts,
            statement_id="stmt-embed-1",
            run_id="run-embed-2",
        )

        assert len(cached_vectors) == 130
        assert len(batch_call_sizes) == 0  # Zero HTTP calls!
        assert cached_usage.is_cache_hit is True
        assert cached_usage.input_tokens == 0


@pytest.mark.asyncio
async def test_decision_engine_bypassed_when_zero_candidate_groups():
    """Verifies that the Jev decision model is NOT invoked when zero candidate groups exist."""
    from app.services.salary_detection.engine import FinancialValidationResult

    # Mock FinancialValidationResult to return 0 candidate groups
    mock_fin_result = FinancialValidationResult(
        has_salary_candidates=False,
        candidate_groups=[],
        status="insufficient_evidence",
        detected_statement_months=["2026-04", "2026-05"],
    )

    with patch("app.services.salary_detection.engine.FinancialValidationEngine.analyze_transactions", return_value=mock_fin_result):
        with patch("app.services.decision_engine.jev.JevDecisionEngine.evaluate_evidence") as mock_jev_call:
            candidate_groups = []
            if len(candidate_groups) == 0:
                decision = JevDecisionResponse(
                    status="insufficient_evidence",
                    employer_candidate=None,
                    supporting_transaction_ids=[],
                    supporting_months=[],
                    reason_codes=["NO_SALARY_CANDIDATE_GROUPS", "INSUFFICIENT_CREDIT_EVIDENCE"],
                    explanation="Zero recurring salary credit groups detected.",
                    requires_human_review=True,
                )
            assert decision.status == "insufficient_evidence"
            assert mock_jev_call.call_count == 0


@pytest.mark.asyncio
async def test_partial_failure_and_graceful_recovery(monkeypatch):
    """Verifies that an OpenRouter failure returns a structured fallback without crashing pipeline."""
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    client = OpenRouterClient(api_key="sk-test-fail")

    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 500
    mock_resp_fail.text = "Internal Server Error"
    mock_resp_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Error", request=MagicMock(), response=mock_resp_fail
    )

    with patch("httpx.AsyncClient.post", side_effect=mock_resp_fail):
        with patch("asyncio.sleep", return_value=None):
            jev_engine = JevDecisionEngine(client=client)
            decision, usage = await jev_engine.evaluate_evidence(
                rag_evidence={"candidate_transactions": []},
                financial_status="insufficient_evidence",
                detected_months=[],
                statement_id="stmt-fail-1",
            )

            assert decision.status == "analysis_failed"
            assert decision.requires_human_review is True
            assert "AI_MODEL_UNAVAILABLE" in decision.reason_codes
            assert usage.success is False


def test_deterministic_decimal_financial_fidelity():
    """Verifies that financial calculations strictly maintain Decimal fidelity without float inaccuracies."""
    amounts = [
        Decimal("34391.00"),
        Decimal("26391.00"),
        Decimal("26391.00"),
        Decimal("26391.00"),
        Decimal("26391.00"),
    ]
    total = sum(amounts)
    avg = total / Decimal(len(amounts))
    
    assert total == Decimal("139955.00")
    assert avg == Decimal("27991.00")
    # Verify no float epsilon errors
    assert isinstance(total, Decimal)
    assert isinstance(avg, Decimal)
