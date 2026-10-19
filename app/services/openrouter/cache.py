"""
SalaryLens AI by CodeSec — AI Response Caching Layer
Caches semantic classification and decision engine results keyed by
(statement_id, sorted_candidate_ids, model_name, processing_version)
to eliminate redundant OpenRouter API token consumption.
"""
import hashlib
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from app.core.config import settings
from app.schemas.openrouter import AIModelCallResult

logger = logging.getLogger("salarylens.ai_cache")


class AIResponseCache:
    """
    Two-tier caching service (Redis + in-memory fallback) for AI model responses.
    """
    _redis_client: Optional[aioredis.Redis] = None
    _in_memory_cache: Dict[str, Dict[str, Any]] = {}
    _MAX_IN_MEMORY_ITEMS = 500

    @classmethod
    def _get_redis(cls) -> Optional[aioredis.Redis]:
        if cls._redis_client is None and settings.REDIS_URL:
            try:
                cls._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
            except Exception as e:
                logger.warning(f"Could not initialize Redis client for AI cache: {e}")
                cls._redis_client = None
        return cls._redis_client

    @classmethod
    def make_cache_key(
        cls,
        stage: str,
        model: str,
        statement_id: Optional[str] = None,
        candidate_keys: Optional[List[str]] = None,
        messages_payload: Optional[str] = None,
        version: Optional[str] = None,
    ) -> str:
        """
        Generates a deterministic cache key using statement-processing version,
        model name, stage, and content hash.
        """
        proc_version = version or settings.STATEMENT_PROCESSING_VERSION
        hasher = hashlib.sha256()
        hasher.update(proc_version.encode("utf-8"))
        hasher.update(stage.encode("utf-8"))
        hasher.update(model.encode("utf-8"))

        if statement_id:
            hasher.update(str(statement_id).encode("utf-8"))
        if candidate_keys:
            hasher.update("::".join(sorted(candidate_keys)).encode("utf-8"))
        if messages_payload:
            hasher.update(messages_payload.encode("utf-8"))

        digest = hasher.hexdigest()[:32]
        clean_model = model.replace("/", "_").replace(":", "_")
        stmt_prefix = str(statement_id) if statement_id else "global"
        return f"salarylens:ai_cache:{proc_version}:{stmt_prefix}:{stage}:{clean_model}:{digest}"

    @classmethod
    async def get(cls, cache_key: str) -> Optional[AIModelCallResult]:
        """
        Retrieves a cached AI result if available, returning an AIModelCallResult
        with cached_tokens recorded and zero additional cost.
        """
        if not settings.AI_EVALUATION_CACHE_ENABLED:
            return None

        cached_data: Optional[Dict[str, Any]] = None

        # 1. Check Redis
        redis_conn = cls._get_redis()
        if redis_conn:
            try:
                raw_json = await redis_conn.get(cache_key)
                if raw_json:
                    cached_data = json.loads(raw_json)
            except Exception as e:
                logger.debug(f"Redis get error in AI cache: {e}")

        # 2. Check in-memory fallback
        if not cached_data and cache_key in cls._in_memory_cache:
            cached_data = cls._in_memory_cache[cache_key]

        if not cached_data:
            return None

        try:
            orig_input = cached_data.get("input_tokens", 0)
            orig_output = cached_data.get("output_tokens", 0)
            return AIModelCallResult(
                model_name=cached_data.get("model_name", "cached-model"),
                actual_model=cached_data.get("model_name", "cached-model"),
                stage=cached_data.get("stage", "cache"),
                raw_response=cached_data.get("raw_response", {}),
                parsed_json=cached_data.get("parsed_json"),
                input_tokens=0,
                output_tokens=0,
                cached_tokens=orig_input + orig_output,
                provider_cost_usd=Decimal("0.00"),
                estimated_cost_usd=Decimal("0.00"),
                latency_ms=1,
                retry_count=0,
                is_simulated=False,
                success=True,
                is_cache_hit=True,
            )
        except Exception as e:
            logger.warning(f"Failed to deserialize cached AI result for {cache_key}: {e}")
            return None

    @classmethod
    async def set(
        cls,
        cache_key: str,
        result: AIModelCallResult,
        ttl_seconds: int = 86400,
    ) -> bool:
        """
        Saves a successful AIModelCallResult to cache with TTL.
        """
        if not settings.AI_EVALUATION_CACHE_ENABLED:
            return False
        if not result.success or not result.parsed_json:
            return False

        serializable_data = {
            "model_name": result.model_name,
            "stage": result.stage,
            "raw_response": result.raw_response,
            "parsed_json": result.parsed_json,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

        # 1. Save to Redis
        redis_conn = cls._get_redis()
        if redis_conn:
            try:
                await redis_conn.setex(
                    cache_key,
                    ttl_seconds,
                    json.dumps(serializable_data, default=str),
                )
            except Exception as e:
                logger.debug(f"Redis setex error in AI cache: {e}")

        # 2. Save to in-memory fallback
        if len(cls._in_memory_cache) >= cls._MAX_IN_MEMORY_ITEMS:
            first_key = next(iter(cls._in_memory_cache))
            cls._in_memory_cache.pop(first_key, None)
        cls._in_memory_cache[cache_key] = serializable_data

        return True

    @classmethod
    async def invalidate_statement(cls, statement_id: str) -> int:
        """
        Invalidates all cached entries for a specific statement ID.
        Used when source data, rules, or model configurations change.
        """
        invalidated_count = 0
        # Invalidate in-memory
        keys_to_del = [k for k in cls._in_memory_cache if statement_id in k]
        for k in keys_to_del:
            cls._in_memory_cache.pop(k, None)
            invalidated_count += 1

        # Invalidate in Redis
        redis_conn = cls._get_redis()
        if redis_conn:
            try:
                keys = await redis_conn.keys(f"salarylens:ai_cache:*:{statement_id}:*")
                if keys:
                    await redis_conn.delete(*keys)
                    invalidated_count += len(keys)
            except Exception as e:
                logger.debug(f"Error invalidating statement cache in Redis: {e}")

        logger.info(f"Invalidated {invalidated_count} cache entries for statement {statement_id}")
        return invalidated_count

    @classmethod
    async def clear_cache(cls) -> None:
        """Clears both Redis and in-memory caches (for testing and migrations)."""
        cls._in_memory_cache.clear()
        redis_conn = cls._get_redis()
        if redis_conn:
            try:
                keys = await redis_conn.keys("salarylens:ai_cache:*")
                if keys:
                    await redis_conn.delete(*keys)
            except Exception as e:
                logger.debug(f"Error clearing Redis cache: {e}")
