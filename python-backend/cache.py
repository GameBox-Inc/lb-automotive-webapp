"""
Redis caching layer with automatic fallback and TTL management
"""
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from prometheus_client import Counter, Histogram
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
cache_hits = Counter('cache_hits_total', 'Total cache hits', ['key_prefix'])
cache_misses = Counter('cache_misses_total', 'Total cache misses', ['key_prefix'])
cache_errors = Counter('cache_errors_total', 'Total cache errors', ['operation'])
cache_latency = Histogram('cache_latency_seconds', 'Cache operation latency', ['operation'])

import os

# Redis connection pool
redis_client: Optional[redis.Redis] = None
redis_disabled: bool = False

async def get_redis() -> Optional[redis.Redis]:
    """Get Redis client with connection pooling"""
    global redis_client, redis_disabled
    
    if redis_disabled:
        return None

    if redis_client is None:
        try:
            host = os.getenv("REDIS_HOST", "localhost")
            redis_client = redis.Redis(
                host=host,
                port=6379,
                db=0,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            await redis_client.ping()
            logger.info(f"Redis connection established at {host}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            logger.warning("Disabling Redis cache for this session")
            cache_errors.labels(operation='connect').inc()
            redis_disabled = True
            return None
    return redis_client

def cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from prefix and arguments"""
    key_parts = [prefix]
    if args:
        key_parts.extend([str(arg) for arg in args])
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        key_parts.extend([f"{k}:{v}" for k, v in sorted_kwargs])
    return ":".join(key_parts)

async def get_cached(key: str) -> Optional[Any]:
    """Get value from cache"""
    client = await get_redis()
    if not client:
        return None
    
    with cache_latency.labels(operation='get').time():
        try:
            value = await client.get(key)
            if value:
                cache_hits.labels(key_prefix=key.split(':')[0]).inc()
                return json.loads(value)
            cache_misses.labels(key_prefix=key.split(':')[0]).inc()
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            cache_errors.labels(operation='get').inc()
            return None

async def set_cached(key: str, value: Any, ttl: int = 300) -> bool:
    """Set value in cache with TTL (default 5 minutes)"""
    client = await get_redis()
    if not client:
        return False
    
    with cache_latency.labels(operation='set').time():
        try:
            await client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            cache_errors.labels(operation='set').inc()
            return False

async def delete_cached(pattern: str) -> int:
    """Delete keys matching pattern"""
    client = await get_redis()
    if not client:
        return 0
    
    with cache_latency.labels(operation='delete').time():
        try:
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete error for pattern {pattern}: {e}")
            cache_errors.labels(operation='delete').inc()
            return 0

def cached(ttl: int = 300, key_prefix: str = "default"):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(key_prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = await get_cached(key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            await set_cached(key, result, ttl)
            return result
        return wrapper
    return decorator

async def invalidate_cache(pattern: str):
    """Invalidate cache keys matching pattern"""
    deleted = await delete_cached(pattern)
    logger.info(f"Invalidated {deleted} cache keys matching '{pattern}'")
    return deleted

# Cache TTLs (in seconds)
TTL_SERVICES = 3600        # 1 hour - services rarely change
TTL_CATEGORIES = 86400     # 24 hours - categories very static
TTL_APPOINTMENTS = 300     # 5 minutes - frequently updated
TTL_USER = 900             # 15 minutes - user profiles
TTL_METRICS = 600          # 10 minutes - dashboard metrics
TTL_IVR = 120              # 2 minutes - active call states
