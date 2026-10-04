"""
src/session_manager.py - Thread-safe session state cache with Redis or In-Memory fallback.
"""
import time
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionBroker:
    """Manages synchronized session state between the browser worker and API clients."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self._in_memory_state: Dict[str, Any] = {}
        self._redis = None

    async def initialize(self):
        """Connect to Redis if configured, otherwise use in-memory state."""
        if self.redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self.redis_url)
                await self._redis.ping()
                logger.info("Connected to Redis session store.")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}), falling back to in-memory store.")
                self._redis = None

    async def get_session(self, key: str = "comix_session") -> Optional[Dict[str, Any]]:
        """Retrieve active session payload."""
        if self._redis:
            data = await self._redis.get(key)
            return json.loads(data) if data else None

        entry = self._in_memory_state.get(key)
        if not entry:
            return None
        # Check TTL
        if entry.get("expires_at", 0) < time.time():
            return None
        return entry

    async def set_session(self, key: str = "comix_session", payload: Optional[Dict[str, Any]] = None, ttl: int = 3600):
        """Save validated session state."""
        if not payload:
            return
        payload["updated_at"] = time.time()
        payload["expires_at"] = time.time() + ttl

        if self._redis:
            await self._redis.set(key, json.dumps(payload), ex=ttl)
        else:
            self._in_memory_state[key] = payload

    async def invalidate(self, key: str = "comix_session"):
        """Invalidate stale or challenged session."""
        if self._redis:
            await self._redis.delete(key)
        else:
            self._in_memory_state.pop(key, None)
