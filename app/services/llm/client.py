"""
SalaryLens AI by CodeSec — Local LLM Client & Unified Inference Provider
Supports local models (Ollama / GGUF on Metal GPU) with automatic fallback to OpenRouter.
"""
from decimal import Decimal
import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.openrouter.client import AIModelCallResult, OpenRouterClient

logger = logging.getLogger("salarylens.llm.local")


class LocalLLMClient:
    """
    Unified local inference client for Ollama and local runtimes.
    Supports structured JSON enforcement, performance telemetry (TTFT, tokens/sec, RAM),
    health checks, model offloading, and seamless fallback to OpenRouter.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
        fallback_client: Optional[OpenRouterClient] = None,
    ):
        self.base_url = (base_url or getattr(settings, "LOCAL_LLM_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.default_model = default_model or getattr(settings, "LOCAL_LLM_MODEL", "qwen2.5:1.5b")
        self.timeout = timeout or getattr(settings, "LOCAL_LLM_TIMEOUT_SECONDS", 120.0)
        self.fallback_client = fallback_client or OpenRouterClient()

    async def is_available(self) -> bool:
        """Checks whether the local LLM runtime (e.g. Ollama) is reachable and healthy."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_available_models(self) -> List[str]:
        """Queries the local runtime for loaded or available model tags."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.warning(f"Could not retrieve local models list: {e}")
        return []

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        stage: str = "extraction",
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        statement_id: Optional[str] = None,
        run_id: Optional[str] = None,
        accumulated_cost: Decimal = Decimal("0.00"),
    ) -> AIModelCallResult:
        """
        Executes a chat completion against the local inference runtime.
        If local runtime is unreachable, disabled, or fails, falls back gracefully to OpenRouter.
        """
        # Determine actual model identifier for local inference vs OpenRouter
        if model and "/" not in model:
            chosen_model = model
        else:
            chosen_model = getattr(settings, "LOCAL_LLM_MODEL", self.default_model)

        provider = getattr(settings, "LOCAL_LLM_PROVIDER", "ollama")

        # Check if local provider is requested
        if provider == "openrouter":
            logger.info("LOCAL_LLM_PROVIDER set to openrouter; routing to OpenRouter cloud directly.")
            return await self.fallback_client.generate_chat_completion(
                messages=messages,
                model=model or settings.SALARY_FINDER_MODEL,
                stage=stage,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
                statement_id=statement_id,
                run_id=run_id,
                accumulated_cost=accumulated_cost,
            )

        start_time = time.time()
        try:
            # Build Ollama chat payload
            payload: Dict[str, Any] = {
                "model": chosen_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            # Enforce JSON formatting if requested
            if response_format and response_format.get("type") == "json_object":
                payload["format"] = "json"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

            if resp.status_code != 200:
                raise RuntimeError(f"Local LLM HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract generated content
            msg = data.get("message", {})
            content = (msg.get("content") or "").strip()

            # Parse JSON content
            parsed_json = None
            clean_text = content
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

            # Telemetry metrics from Ollama
            prompt_tokens = data.get("prompt_eval_count", len(str(messages)) // 4)
            completion_tokens = data.get("eval_count", len(content) // 4)
            eval_duration_ns = data.get("eval_duration", 0)
            tokens_per_sec = (completion_tokens / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0

            logger.info(
                f"[Local LLM] Model: {chosen_model} | Tokens: {prompt_tokens} in / {completion_tokens} out "
                f"({tokens_per_sec:.1f} tps) | Latency: {latency_ms}ms | Cost: ₹0.00 (Local Hardware)"
            )

            return AIModelCallResult(
                model_name=chosen_model,
                actual_model=chosen_model,
                stage=stage,
                statement_id=statement_id,
                run_id=run_id,
                raw_response=data,
                parsed_json=parsed_json,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cached_tokens=0,
                provider_cost_usd=Decimal("0.00"),
                estimated_cost_usd=Decimal("0.00"),
                latency_ms=latency_ms,
                retry_count=0,
                is_simulated=False,
                is_cache_hit=False,
                success=True,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"Local LLM call failed for model {chosen_model} ({type(e).__name__}: {str(e)}). Falling back to OpenRouter..."
            )
            # Execute graceful fallback to OpenRouter
            try:
                fallback_model = settings.SALARY_FINDER_MODEL if stage == "extraction" else settings.DECISION_MODEL
                fallback_res = await self.fallback_client.generate_chat_completion(
                    messages=messages,
                    model=fallback_model,
                    stage=stage,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    statement_id=statement_id,
                    run_id=run_id,
                    accumulated_cost=accumulated_cost,
                )
                fallback_res.model_name = f"{chosen_model}->fallback:{fallback_model}"
                return fallback_res
            except Exception as fb_err:
                logger.error(f"Fallback to OpenRouter also failed: {fb_err}")
                return AIModelCallResult(
                    model_name=chosen_model,
                    actual_model=chosen_model,
                    stage=stage,
                    statement_id=statement_id,
                    run_id=run_id,
                    raw_response={},
                    parsed_json=None,
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    provider_cost_usd=Decimal("0.00"),
                    estimated_cost_usd=Decimal("0.00"),
                    latency_ms=latency_ms,
                    retry_count=0,
                    is_simulated=False,
                    is_cache_hit=False,
                    success=False,
                    error_message=f"Local LLM error: {str(e)}; Fallback error: {str(fb_err)}",
                )
