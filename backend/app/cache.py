"""Redis-based cache manager for ArabSeed scraper data."""
import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
import redis
from app.config import settings


class CacheManager:
    """Thread-safe Redis cache manager with automatic serialization."""

    def __init__(self):
        """Initialize Redis connection."""
        self._redis = None
        self._enabled = True

    @property
    def redis(self) -> redis.Redis:
        """Get Redis client, creating connection if needed."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self._redis.ping()
                print("[Cache] Connected to Redis")
            except Exception as e:
                print(f"[Cache] Redis connection failed: {e}")
                self._enabled = False
                # Return a dummy client that does nothing
                return DummyRedis()
        return self._redis

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self._enabled:
            return None

        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"[Cache] Error getting key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (default: 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            return False

        try:
            serialized = json.dumps(value)
            self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            print(f"[Cache] Error setting key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            return False

        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"[Cache] Error deleting key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "search:*")

        Returns:
            Number of keys deleted
        """
        if not self._enabled:
            return 0

        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            print(f"[Cache] Error deleting pattern {pattern}: {e}")
            return 0

    def clear_all(self) -> bool:
        """Clear all cache entries.

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            return False

        try:
            self.redis.flushdb()
            return True
        except Exception as e:
            print(f"[Cache] Error clearing cache: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self._enabled:
            return {"enabled": False}

        try:
            info = self.redis.info("stats")
            keyspace = self.redis.info("keyspace")

            total_keys = 0
            if "db0" in keyspace:
                total_keys = keyspace["db0"].get("keys", 0)

            return {
                "enabled": True,
                "total_keys": total_keys,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            print(f"[Cache] Error getting stats: {e}")
            return {"enabled": False, "error": str(e)}

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses

        Returns:
            Hit rate as percentage (0-100)
        """
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100


class DummyRedis:
    """Dummy Redis client that does nothing (used when Redis is unavailable)."""

    def get(self, key):
        return None

    def setex(self, key, ttl, value):
        pass

    def delete(self, *keys):
        return 0

    def keys(self, pattern):
        return []

    def flushdb(self):
        pass

    def info(self, section):
        return {}

    def ping(self):
        return True


# Global cache instance
cache = CacheManager()


def cached(key_prefix: str, ttl: int = 300):
    """Decorator for caching function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds

    Example:
        @cached("search", ttl=600)
        async def search(query: str):
            # expensive operation
            return results
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            cache_key = _generate_cache_key(key_prefix, args, kwargs)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                print(f"[Cache] HIT: {cache_key}")
                return cached_result

            # Cache miss - call function
            print(f"[Cache] MISS: {cache_key}")
            result = await func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, ttl=ttl)

            return result
        return wrapper
    return decorator


def _generate_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function arguments.

    Args:
        prefix: Key prefix
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    # Skip 'self' argument for methods
    args_to_hash = args[1:] if args and hasattr(args[0], '__class__') else args

    # Create a string representation of arguments
    key_parts = [str(arg) for arg in args_to_hash]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)

    # Hash long keys
    if len(key_string) > 100:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    return f"{prefix}:{key_string}"
