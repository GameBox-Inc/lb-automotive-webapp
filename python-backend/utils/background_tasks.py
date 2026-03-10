import json
import logging
import asyncio
from typing import Dict, Any
from llm_service import classify_intent
from security import redis_client
from utils.ivr_helper import get_redis_result_key

logger = logging.getLogger(__name__)

async def process_ivr_intent_async(call_sid: str, speech_text: str):
    """
    Background task to process intent and store in Redis.
    """
    start_time = asyncio.get_event_loop().time()
    try:
        logger.info(f"Async processing intent for {call_sid}: {speech_text}")
        
        # Run classification in a thread pool since it's synchronous requests-based
        loop = asyncio.get_event_loop()
        llm_result = await loop.run_in_executor(None, classify_intent, speech_text)
        
        # Store result in Redis (valid for 2 minutes)
        if redis_client:
            redis_key = get_redis_result_key(call_sid)
            redis_client.setex(redis_key, 120, json.dumps(llm_result))
            
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
