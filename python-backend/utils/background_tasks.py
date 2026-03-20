import json
import logging
import asyncio
import functools
import os
from typing import Dict, Any, Optional
from services.llm import classify_intent
from security import redis_client
from utils.ivr_helper import get_redis_result_key
from observability.tracing import restore_trace_context, update_phase, PHASE_LLM_STARTED, PHASE_LLM_COMPLETE

logger = logging.getLogger(__name__)

# Limit concurrent LLM classification work per backend process.
# This prevents bursts of Twilio calls from overwhelming CPU threadpool and/or Anthropic rate limits.
_LLM_CONCURRENCY_LIMIT = max(1, int(os.getenv("IVR_LLM_CONCURRENCY_LIMIT", "4")))
_llm_classify_semaphore = asyncio.Semaphore(_LLM_CONCURRENCY_LIMIT)


async def process_ivr_intent_async(
    call_sid: str,
    speech_text: str,
    trace_ctx: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[str] = None,
):
    """
    Background task to process intent and store in Redis.
    Restores trace context so logs include callSid, requestId, etc.
    conversation_context: optional "Last intent: X, step: Y" for follow-up resolution.
    """
    if trace_ctx:
        restore_trace_context(trace_ctx)
    update_phase(PHASE_LLM_STARTED)
    start_time = asyncio.get_event_loop().time()
    try:
        logger.info(f"Async processing intent for {call_sid}: {speech_text}", extra={"conversation_context": conversation_context})
        loop = asyncio.get_event_loop()
        # Bound expensive LLM classification concurrency per process.
        async with _llm_classify_semaphore:
            llm_result = await loop.run_in_executor(
                None, functools.partial(classify_intent, speech_text, conversation_context)
            )
        
        # Store result in Redis (valid for 2 minutes)
        if redis_client:
            redis_key = get_redis_result_key(call_sid)
            redis_client.setex(redis_key, 120, json.dumps(llm_result))
            update_phase(PHASE_LLM_COMPLETE)
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            logger.info(f"LATENCY_TRACK: AI processing for {call_sid} took {duration:.2f}s")
        else:
            logger.error("Redis unreachable for async IVR result")
            
    except Exception as e:
        logger.error(f"Error in async IVR processing: {e}")
        # Store an error state in Redis so the UI knows to fallback
        if redis_client:
            redis_client.setex(get_redis_result_key(call_sid), 120, json.dumps({"intent": "error", "error": str(e)}))
