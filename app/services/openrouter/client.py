"""
SalaryLens AI by CodeSec — OpenRouter API Client
"""
import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.schemas.openrouter import AIModelCallResult
from app.services.openrouter.pricing import ModelPricingRegistry

logger = logging.getLogger("salarylens.openrouter")


class OpenRouterConfigError(Exception):
    """Raised when OpenRouter credentials or configuration are invalid."""
    pass


class OpenRouterBudgetExceededError(Exception):
    """Raised when a statement's AI budget ceiling is reached."""
    pass


class OpenRouterClient:
    """
    Robust OpenRouter client with bounded retries, exponential backoff,
    latency tracking, token counting, cost tracking, and demo mode simulation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        self.timeout = settings.OPENROUTER_REQUEST_TIMEOUT_SECONDS
        self.max_retries = settings.OPENROUTER_MAX_RETRIES
        self.backoff_factor = settings.OPENROUTER_RETRY_BACKOFF_FACTOR

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        stage: str,
        response_format: Optional[Dict[str, str]] = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        statement_id: Optional[str] = None,
        run_id: Optional[str] = None,
        accumulated_cost: Decimal = Decimal("0.00"),
    ) -> AIModelCallResult:
        """
        Executes a chat completion request through OpenRouter.
        Enforces statement-level budget limits before making the call.
        Emits auditable per-request usage logs with statement ID, run ID, actual model, tokens, and cost.
        """
        # 1. Budget enforcement check
        if accumulated_cost >= Decimal(str(settings.MAX_AI_COST_USD_PER_STATEMENT)):
            raise OpenRouterBudgetExceededError(
                f"AI budget of ${settings.MAX_AI_COST_USD_PER_STATEMENT} exceeded for statement {statement_id}."
            )

        # 2. Check AI Response Cache
        cache_key: Optional[str] = None
        if settings.AI_EVALUATION_CACHE_ENABLED:
            from app.services.openrouter.cache import AIResponseCache
            msgs_str = json.dumps(messages, sort_keys=True, separators=(',', ':'))
            cache_key = AIResponseCache.make_cache_key(
                stage=stage,
                model=model,
                statement_id=statement_id,
                messages_payload=msgs_str,
            )
            cached_result = await AIResponseCache.get(cache_key)
            if cached_result is not None:
                cached_result.statement_id = statement_id
                cached_result.run_id = run_id
                cached_result.is_cache_hit = True
                logger.info(
                    f"[OpenRouter Usage] Run: {run_id or 'N/A'} | Stmt: {statement_id or 'N/A'} | Stage: {stage} | Model: {cached_result.model_name} | Tokens: 0 in / 0 out ({cached_result.cached_tokens} cached) | Cost: $0.00 | Retries: 0 | Latency: {cached_result.latency_ms}ms | Cache: HIT",
                    extra={
                        "statement_id": statement_id,
                        "run_id": run_id,
                        "stage": stage,
                        "requested_model": model,
                        "actual_model": cached_result.actual_model or model,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cached_tokens": cached_result.cached_tokens,
                        "provider_cost_usd": "0.00",
                        "estimated_cost_usd": "0.00",
                        "retry_count": 0,
                        "latency_ms": cached_result.latency_ms,
                        "cache_hit": True,
                    }
                )
                return cached_result

        # 3. Demo Mode Simulation
        if settings.DEMO_MODE or not self.api_key:
            if not settings.DEMO_MODE and not self.api_key:
                raise OpenRouterConfigError(
                    "OPENROUTER_API_KEY is not configured and DEMO_MODE is disabled. Cannot proceed with AI request."
                )
            sim_res = self._simulate_demo_response(messages, model, stage)
            sim_res.statement_id = statement_id
            sim_res.run_id = run_id
            sim_res.actual_model = model
            sim_res.is_cache_hit = False
            logger.info(
                f"[OpenRouter Usage] Run: {run_id or 'N/A'} | Stmt: {statement_id or 'N/A'} | Stage: {stage} | Model: {model} (Demo) | Tokens: {sim_res.input_tokens} in / {sim_res.output_tokens} out | Cost: $0.00 | Retries: 0 | Latency: {sim_res.latency_ms}ms | Cache: MISS",
                extra={
                    "statement_id": statement_id,
                    "run_id": run_id,
                    "stage": stage,
                    "requested_model": model,
                    "actual_model": model,
                    "input_tokens": sim_res.input_tokens,
                    "output_tokens": sim_res.output_tokens,
                    "cached_tokens": 0,
                    "provider_cost_usd": "0.00",
                    "estimated_cost_usd": "0.00",
                    "retry_count": 0,
                    "latency_ms": sim_res.latency_ms,
                    "cache_hit": False,
                }
            )
            if cache_key and settings.AI_EVALUATION_CACHE_ENABLED and sim_res.success:
                from app.services.openrouter.cache import AIResponseCache
                await AIResponseCache.set(cache_key, sim_res)
            return sim_res

        # 4. Live OpenRouter Call
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_APP_NAME,
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        retry_count = 0
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                if resp.status_code in [429, 500, 502, 503, 504] and attempt < self.max_retries:
                    retry_count += 1
                    sleep_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"OpenRouter returned status {resp.status_code}. Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{self.max_retries})."
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                resp.raise_for_status()
                response_data = resp.json()
                latency_ms = int((time.time() - start_time) * 1000)

                # Extract actual model returned by OpenRouter
                actual_model = response_data.get("model") or model

                # Extract token usage
                usage = response_data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

                # Extract provider cost if available or calculate estimated
                provider_cost = None
                if "cost" in response_data:
                    try:
                        provider_cost = Decimal(str(response_data["cost"])).quantize(Decimal("0.000001"))
                    except Exception:
                        provider_cost = None

                estimated_cost = ModelPricingRegistry.calculate_estimated_cost(
                    model, prompt_tokens, completion_tokens
                )

                # Parse JSON content if available
                content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed_json = None
                clean_text = content.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    clean_text = "\n".join(lines).strip()

                try:
                    parsed_json = json.loads(clean_text)
                except Exception:
                    import re
                    json_match = re.search(r"(\{.*\}|\[.*\])", clean_text, re.DOTALL)
                    if json_match:
                        try:
                            parsed_json = json.loads(json_match.group(1))
                        except Exception:
                            pass

                result = AIModelCallResult(
                    model_name=model,
                    actual_model=actual_model,
                    stage=stage,
                    statement_id=statement_id,
                    run_id=run_id,
                    raw_response=response_data,
                    parsed_json=parsed_json,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    cached_tokens=cached_tokens,
                    provider_cost_usd=provider_cost,
                    estimated_cost_usd=estimated_cost,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                    is_simulated=False,
                    is_cache_hit=False,
                    success=True,
                )

                # Emit per-request usage log
                cost_display = provider_cost if provider_cost is not None else estimated_cost
                logger.info(
                    f"[OpenRouter Usage] Run: {run_id or 'N/A'} | Stmt: {statement_id or 'N/A'} | Stage: {stage} | Model: {actual_model} (req: {model}) | Tokens: {prompt_tokens} in / {completion_tokens} out | Cost: ${cost_display} | Retries: {retry_count} | Latency: {latency_ms}ms | Cache: MISS",
                    extra={
                        "statement_id": statement_id,
                        "run_id": run_id,
                        "stage": stage,
                        "requested_model": model,
                        "actual_model": actual_model,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "cached_tokens": cached_tokens,
                        "provider_cost_usd": str(provider_cost) if provider_cost else None,
                        "estimated_cost_usd": str(estimated_cost),
                        "retry_count": retry_count,
                        "latency_ms": latency_ms,
                        "cache_hit": False,
                    }
                )

                if cache_key and settings.AI_EVALUATION_CACHE_ENABLED and result.parsed_json:
                    from app.services.openrouter.cache import AIResponseCache
                    await AIResponseCache.set(cache_key, result)
                return result

            except httpx.HTTPStatusError as e:
                if attempt == self.max_retries:
                    latency_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"OpenRouter request failed with status {e.response.status_code}: {e.response.text}")
                    return AIModelCallResult(
                        model_name=model,
                        actual_model=model,
                        stage=stage,
                        statement_id=statement_id,
                        run_id=run_id,
                        raw_response={},
                        latency_ms=latency_ms,
                        retry_count=retry_count,
                        is_simulated=False,
                        is_cache_hit=False,
                        success=False,
                        error_message=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                    )
            except Exception as e:
                if attempt == self.max_retries:
                    latency_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"OpenRouter connection error: {str(e)}")
                    return AIModelCallResult(
                        model_name=model,
                        actual_model=model,
                        stage=stage,
                        statement_id=statement_id,
                        run_id=run_id,
                        raw_response={},
                        latency_ms=latency_ms,
                        retry_count=retry_count,
                        is_simulated=False,
                        is_cache_hit=False,
                        success=False,
                        error_message=str(e),
                    )

        # Fallback if loop completes unexpectedly
        return AIModelCallResult(
            model_name=model,
            actual_model=model,
            stage=stage,
            statement_id=statement_id,
            run_id=run_id,
            raw_response={},
            is_simulated=False,
            is_cache_hit=False,
            success=False,
            error_message="Maximum retries exceeded without successful response.",
        )

    def _simulate_demo_response(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        stage: str,
    ) -> AIModelCallResult:
        """
        Generates deterministic, schema-compliant synthetic responses for DEMO_MODE.
        Simulated metrics are strictly labeled is_simulated=True.
        """
        user_prompt = ""
        for m in messages:
            if m.get("role") == "user":
                user_prompt += str(m.get("content", ""))

        if stage == "extraction":
            synthetic_payload = {
                "account_holder": "Alex Morgan",
                "account_number_last4": "4491",
                "detected_statement_period": "2026-03-01 to 2026-05-31",
                "transactions": [
                    {
                        "transaction_date": "2026-03-02",
                        "description": "GROCERY MART #104",
                        "debit_amount": "84.20",
                        "credit_amount": None,
                        "currency": "USD",
                        "page_number": 1,
                        "is_salary_candidate": False,
                        "confidence": 0.05
                    },
                    {
                        "transaction_date": "2026-03-31",
                        "description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP",
                        "debit_amount": None,
                        "credit_amount": "5250.00",
                        "currency": "USD",
                        "page_number": 1,
                        "potential_employer": "Acme Tech Corp",
                        "employer_aliases": ["ACME TECH CORP", "ACME TECH CORP SALARY"],
                        "is_salary_candidate": True,
                        "confidence": 0.95
                    },
                    {
                        "transaction_date": "2026-04-30",
                        "description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP",
                        "debit_amount": None,
                        "credit_amount": "5250.00",
                        "currency": "USD",
                        "page_number": 1,
                        "potential_employer": "Acme Tech Corp",
                        "employer_aliases": ["ACME TECH CORP", "ACME TECH CORP SALARY"],
                        "is_salary_candidate": True,
                        "confidence": 0.95
                    },
                    {
                        "transaction_date": "2026-05-12",
                        "description": "WIRE TRANSFER INCOMING FAMILY",
                        "debit_amount": None,
                        "credit_amount": "200.00",
                        "currency": "USD",
                        "page_number": 1,
                        "is_salary_candidate": False,
                        "confidence": 0.10
                    },
                    {
                        "transaction_date": "2026-05-30",
                        "description": "ACH CREDIT ACME TECH CORP SALARY DIR DEP",
                        "debit_amount": None,
                        "credit_amount": "5250.00",
                        "currency": "USD",
                        "page_number": 1,
                        "potential_employer": "Acme Tech Corp",
                        "employer_aliases": ["ACME TECH CORP", "ACME TECH CORP SALARY"],
                        "is_salary_candidate": True,
                        "confidence": 0.95
                    }
                ],
                "uncertainties": []
            }
        else:
            # stage == "decision"
            synthetic_payload = {
                "status": "likely_salary",
                "employer_candidate": "Acme Tech Corp",
                "supporting_transaction_ids": [],  # Filled by caller or grounding logic
                "supporting_months": ["2026-03", "2026-04", "2026-05"],
                "reason_codes": [
                    "REGULAR_MONTHLY_CADENCE",
                    "IDENTICAL_SALARY_AMOUNT",
                    "RECOGNIZED_EMPLOYER_NAME"
                ],
                "explanation": "Three consecutive monthly credits of $5,250.00 received from Acme Tech Corp on end-of-month dates.",
                "uncertainties": [],
                "requires_human_review": False
            }

        simulated_input_tokens = 950
        simulated_output_tokens = 280
        simulated_cost = ModelPricingRegistry.calculate_estimated_cost(
            model, simulated_input_tokens, simulated_output_tokens
        )

        return AIModelCallResult(
            model_name=model,
            stage=stage,
            raw_response={"simulated": True, "payload": synthetic_payload},
            parsed_json=synthetic_payload,
            input_tokens=simulated_input_tokens,
            output_tokens=simulated_output_tokens,
            cached_tokens=0,
            provider_cost_usd=None,
            estimated_cost_usd=simulated_cost,
            latency_ms=180,
            retry_count=0,
            is_simulated=True,
            success=True,
        )
