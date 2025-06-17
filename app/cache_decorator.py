import json
import hashlib
import logging
from datetime import timedelta
from functools import wraps
import redis
import os

# Redis client for endpoint caching
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        decode_responses=True,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )
    redis_client.ping()
except Exception as e:
    logging.warning(f"Redis connection failed: {e}. Endpoint caching will be disabled.")
    redis_client = None

def cache_endpoint(duration_minutes: int = 5, prefix: str = "endpoint"):
    """
    Decorator for caching endpoint responses
    
    Args:
        duration_minutes: Cache duration in minutes
        prefix: Cache key prefix
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not redis_client:
                return func(*args, **kwargs)
            
            # Generate cache key from function name and arguments
            cache_key_data = {
                'function': func.__name__,
                'args': str(args),
                'kwargs': {k: str(v) for k, v in kwargs.items()}
            }
            cache_key_str = json.dumps(cache_key_data, sort_keys=True)
            cache_key = f"{prefix}:{hashlib.md5(cache_key_str.encode()).hexdigest()}"
            
            try:
                # Try to get from cache
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    logging.info(f"Cache hit for {func.__name__}")
                    return json.loads(cached_result)
            except Exception as e:
                logging.warning(f"Cache retrieval failed for {func.__name__}: {e}")
            
            # Cache miss - execute function
            result = func(*args, **kwargs)
            
            try:
                # Store result in cache
                redis_client.setex(
                    cache_key,
                    timedelta(minutes=duration_minutes),
                    json.dumps(result)
                )
                logging.info(f"Cached result for {func.__name__}")
            except Exception as e:
                logging.warning(f"Cache storage failed for {func.__name__}: {e}")
            
            return result
        return wrapper
    return decorator 