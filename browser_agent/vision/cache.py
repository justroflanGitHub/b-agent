"""
Vision Cache - Caching for visual analysis results.

Provides:
- In-memory caching of analysis results
- Screenshot hash-based lookup
- TTL-based expiration
- Cache statistics
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with timestamp and data."""

    data: Any
    timestamp: float
    access_count: int = 0
    screenshot_hash: str = ""

    def is_expired(self, ttl: float) -> bool:
        """Check if entry has expired."""
        if ttl <= 0:
            return False
        return time.time() - self.timestamp > ttl


class VisionCache:
    """
    LRU Cache for visual analysis results.

    Features:
    - Screenshot hash-based caching
    - Configurable TTL
    - Maximum size with LRU eviction
    - Cache statistics
    - Serialization support
    """

    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0, enabled: bool = True):  # 5 minutes default
        """
        Initialize vision cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (0 = no expiration)
            enabled: Whether caching is enabled
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _hash_screenshot(self, screenshot: bytes) -> str:
        """Generate hash for screenshot."""
        return hashlib.md5(screenshot).hexdigest()

    def _hash_key(self, screenshot: bytes, operation: str, **kwargs) -> str:
        """Generate cache key from screenshot and operation."""
        screenshot_hash = self._hash_screenshot(screenshot)
        # Include operation and relevant kwargs in key
        key_data = {
            "operation": operation,
            "screenshot_hash": screenshot_hash,
            **{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))},
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def get(self, screenshot: bytes, operation: str, **kwargs) -> Optional[Any]:
        """
        Get cached result for operation on screenshot.

        Args:
            screenshot: Screenshot bytes
            operation: Operation name (e.g., "analyze_page", "find_element")
            **kwargs: Additional operation parameters

        Returns:
            Cached result or None if not found/expired
        """
        if not self.enabled:
            return None

        key = self._hash_key(screenshot, operation, **kwargs)

        if key in self._cache:
            entry = self._cache[key]

            # Check expiration
            if entry.is_expired(self.ttl_seconds):
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache expired for {operation}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access_count += 1
            self._hits += 1
            logger.debug(f"Cache hit for {operation}")
            return entry.data

        self._misses += 1
        logger.debug(f"Cache miss for {operation}")
        return None

    def set(self, screenshot: bytes, operation: str, data: Any, **kwargs) -> str:
        """
        Cache result for operation on screenshot.

        Args:
            screenshot: Screenshot bytes
            operation: Operation name
            data: Data to cache
            **kwargs: Additional operation parameters

        Returns:
            Cache key
        """
        if not self.enabled:
            return ""

        key = self._hash_key(screenshot, operation, **kwargs)
        screenshot_hash = self._hash_screenshot(screenshot)

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._evictions += 1
            logger.debug(f"Evicted cache entry (LRU)")

        # Add new entry
        self._cache[key] = CacheEntry(data=data, timestamp=time.time(), screenshot_hash=screenshot_hash)

        logger.debug(f"Cached result for {operation}")
        return key

    def invalidate(self, screenshot: bytes, operation: Optional[str] = None) -> int:
        """
        Invalidate cache entries for a screenshot.

        Args:
            screenshot: Screenshot bytes
            operation: Optional specific operation to invalidate

        Returns:
            Number of entries invalidated
        """
        if not self.enabled:
            return 0

        screenshot_hash = self._hash_screenshot(screenshot)
        keys_to_delete = []

        for key, entry in self._cache.items():
            if entry.screenshot_hash == screenshot_hash:
                if operation is None or operation in key:
                    keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            logger.debug(f"Invalidated {len(keys_to_delete)} cache entries")

        return len(keys_to_delete)

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Vision cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "enabled": self.enabled,
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        if self.ttl_seconds <= 0:
            return 0

        keys_to_delete = []

        for key, entry in self._cache.items():
            if entry.is_expired(self.ttl_seconds):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            logger.debug(f"Cleaned up {len(keys_to_delete)} expired entries")

        return len(keys_to_delete)

    def get_or_compute(self, screenshot: bytes, operation: str, compute_fn, **kwargs) -> Any:
        """
        Get cached result or compute and cache.

        Args:
            screenshot: Screenshot bytes
            operation: Operation name
            compute_fn: Async function to compute result if not cached
            **kwargs: Additional parameters

        Returns:
            Cached or computed result
        """
        cached = self.get(screenshot, operation, **kwargs)
        if cached is not None:
            return cached

        # Compute result
        result = compute_fn()

        # Cache result
        self.set(screenshot, operation, result, **kwargs)

        return result

    async def async_get_or_compute(self, screenshot: bytes, operation: str, compute_fn, **kwargs) -> Any:
        """
        Async version of get_or_compute.

        Args:
            screenshot: Screenshot bytes
            operation: Operation name
            compute_fn: Async function to compute result if not cached
            **kwargs: Additional parameters

        Returns:
            Cached or computed result
        """
        cached = self.get(screenshot, operation, **kwargs)
        if cached is not None:
            return cached

        # Compute result
        result = await compute_fn()

        # Cache result
        self.set(screenshot, operation, result, **kwargs)

        return result

    def export_state(self) -> Dict[str, Any]:
        """Export cache state for serialization."""
        return {
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "enabled": self.enabled,
            "stats": self.get_stats(),
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "VisionCache":
        """Create cache from exported state."""
        return cls(
            max_size=state.get("max_size", 100),
            ttl_seconds=state.get("ttl_seconds", 300.0),
            enabled=state.get("enabled", True),
        )


def create_vision_cache(max_size: int = 100, ttl_seconds: float = 300.0) -> VisionCache:
    """Create a vision cache instance."""
    return VisionCache(max_size=max_size, ttl_seconds=ttl_seconds)
