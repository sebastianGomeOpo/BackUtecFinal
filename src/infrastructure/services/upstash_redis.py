"""
Upstash Redis Compatibility Shim
Provides Redis-like interface using local MemoryStore
Allows existing code to work without changes while using in-memory storage
"""

from typing import Any, Dict, Optional
from ..cache.memory_store import get_store, MemoryStore
import json
import logging

logger = logging.getLogger(__name__)


class RedisShim:
    """
    Redis-compatible interface using MemoryStore
    Provides the same methods used by memory_optimizer.py and sales_agent_v3.py
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or get_store()
        self._memory_ttl = 7200  # 2 hours for memory state
        self._mapping_ttl = 3600  # 1 hour for product mappings

    # ============================================================================
    # Memory State Methods (used by memory_optimizer.py)
    # ============================================================================

    async def get_memory(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get memory state for a conversation
        Used by memory_optimizer.py for fast memory retrieval
        """
        key = f"memory:{conversation_id}"
        data = self._store.get(key)
        if data is None:
            return None
        # If stored as JSON string, parse it
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return data

    async def set_memory(self, conversation_id: str, memory_state: Dict[str, Any]) -> bool:
        """
        Save memory state for a conversation
        Used by memory_optimizer.py to persist conversation state
        """
        key = f"memory:{conversation_id}"
        # Store as dict directly (MemoryStore handles any type)
        return self._store.set(key, memory_state, ttl=self._memory_ttl)

    # ============================================================================
    # Product Mapping Methods (used by sales_agent_v3.py)
    # ============================================================================

    async def get_product_mapping(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product mapping for a conversation
        Used by sales_agent_v3.py to resolve product references (A1, B2, etc.)
        """
        key = f"product_mapping:{conversation_id}"
        data = self._store.get(key)
        if data is None:
            return None
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return data

    async def set_product_mapping(self, conversation_id: str, mapping: Dict[str, Any]) -> bool:
        """
        Save product mapping for a conversation
        Used by sales_agent_v3.py to persist product display mappings
        """
        key = f"product_mapping:{conversation_id}"
        return self._store.set(key, mapping, ttl=self._mapping_ttl)

    # ============================================================================
    # Generic Redis-like Methods (for future compatibility)
    # ============================================================================

    async def get(self, key: str) -> Optional[Any]:
        """Generic get"""
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Generic set with optional TTL"""
        return self._store.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        """Delete key"""
        return self._store.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self._store.exists(key)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on key"""
        return self._store.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get remaining TTL"""
        return self._store.ttl(key)

    # ============================================================================
    # Hash Operations
    # ============================================================================

    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        return self._store.hset(key, field, value)

    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        return self._store.hget(key, field)

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        return self._store.hgetall(key)

    # ============================================================================
    # List Operations
    # ============================================================================

    async def lpush(self, key: str, value: Any) -> int:
        """Push to left of list"""
        return self._store.lpush(key, value)

    async def rpush(self, key: str, value: Any) -> int:
        """Push to right of list"""
        return self._store.rpush(key, value)

    async def lrange(self, key: str, start: int, end: int) -> list:
        """Get range from list"""
        return self._store.lrange(key, start, end)

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim list to range"""
        return self._store.ltrim(key, start, end)


# Global instance
_redis_shim: Optional[RedisShim] = None


def get_redis() -> RedisShim:
    """
    Get Redis-compatible client instance
    This is the main entry point used by other modules
    """
    global _redis_shim
    if _redis_shim is None:
        _redis_shim = RedisShim()
        logger.info("Initialized Redis shim (using local MemoryStore)")
    return _redis_shim


# For compatibility with code that might check Redis availability
REDIS_AVAILABLE = True
