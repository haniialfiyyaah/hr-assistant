"""Redis cache that degrades to a miss on any infrastructure failure."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResilientCache:
    def __init__(self, redis_url: str) -> None:
        self.client = None
        try:
            import redis

            self.client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                decode_responses=True,
            )
        except Exception:
            logger.warning("Redis client init failed; cache will behave as a miss")
            self.client = None

    def health(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def get(self, key: str) -> Any | None:
        if self.client is None:
            return None
        try:
            raw = self.client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.warning("Redis get failed for key=%s; treating as cache miss", key)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self.client is None or ttl_seconds <= 0:
            return
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value))
        except Exception:
            logger.warning("Redis set failed for key=%s; continuing without cache", key)


class NullCache(ResilientCache):
    """No-op cache for offline tests; never opens a Redis connection."""

    def __init__(self) -> None:
        self.client = None

    def health(self) -> bool:
        return False

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None
