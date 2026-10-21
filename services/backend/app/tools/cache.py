"""Thread-safe, bounded in-memory LRU document cache with TTL expiration.

Supports:
- Safe reuse of already persisted/fetched documents.
- Strict freshness rules and configurable TTL (default: 3600 seconds).
- LRU eviction ceiling to prevent unbounded memory growth.
- Cache invalidation and telemetry metrics.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("agentops.tools.cache")
settings = get_settings()


class DocumentCache:
    """Thread-safe bounded in-memory LRU cache with TTL invalidation."""

    def __init__(
        self,
        ttl_seconds: int | None = None,
        max_entries: int | None = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds or settings.HTTP_CACHE_TTL_SECONDS
        self.max_entries = max_entries or settings.HTTP_CACHE_MAX_ENTRIES
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, url: str) -> dict[str, Any] | None:
        """Retrieve a cached document if present and unexpired."""
        norm_url = url.strip().lower()
        now = time.time()

        with self._lock:
            entry = self._cache.get(norm_url)
            if entry is None:
                self._misses += 1
                return None

            # Check TTL freshness
            age = now - entry["timestamp"]
            if age > self.ttl_seconds:
                # Expired -> Purge
                del self._cache[norm_url]
                self._misses += 1
                logger.debug("document_cache_ttl_expired", url=norm_url, age_seconds=round(age, 2))
                return None

            # Cache hit: Move to end (most recently used)
            self._cache.move_to_end(norm_url)
            self._hits += 1
            entry["hit_count"] += 1
            logger.debug(
                "document_cache_hit",
                url=norm_url,
                age_seconds=round(age, 2),
                hit_count=entry["hit_count"],
            )
            return dict(entry["data"])

    def set(self, url: str, data: dict[str, Any], content_hash: str | None = None) -> None:
        """Store document in cache with current timestamp, enforcing max capacity."""
        norm_url = url.strip().lower()
        now = time.time()

        with self._lock:
            if norm_url in self._cache:
                self._cache.move_to_end(norm_url)
            elif len(self._cache) >= self.max_entries:
                # Evict oldest (least recently used)
                oldest_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                logger.debug("document_cache_lru_evicted", evicted_url=oldest_key)

            self._cache[norm_url] = {
                "data": dict(data),
                "timestamp": now,
                "content_hash": content_hash or "",
                "hit_count": 0,
            }
            logger.debug("document_cache_stored", url=norm_url, cache_size=len(self._cache))

    def invalidate(self, url: str) -> bool:
        """Explicitly purge an entry by URL."""
        norm_url = url.strip().lower()
        with self._lock:
            if norm_url in self._cache:
                del self._cache[norm_url]
                logger.info("document_cache_invalidated", url=norm_url)
                return True
            return False

    def clear(self) -> None:
        """Flush the entire cache and reset counters."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            logger.info("document_cache_flushed")

    def get_stats(self) -> dict[str, Any]:
        """Return cache health and telemetry statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_ratio": round(hit_ratio, 4),
            }


# Global singleton instance for public document caching
_global_document_cache = DocumentCache()


def get_document_cache() -> DocumentCache:
    """Retrieve global document cache instance."""
    return _global_document_cache
