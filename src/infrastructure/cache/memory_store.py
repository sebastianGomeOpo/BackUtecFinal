"""
Local Memory Store - Replaces Upstash Redis
Thread-safe in-memory cache with TTL support for sessions, carts, and conversations
"""

import threading
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Thread-safe in-memory key-value store with TTL support
    Replaces Upstash Redis for local development/deployment
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}  # key -> timestamp when it expires
        self._lock = threading.RLock()
        self._cleanup_interval = 60  # seconds between cleanup runs
        self._last_cleanup = time.time()

    def _maybe_cleanup(self):
        """Lazy cleanup - run periodically, not on every operation"""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self):
        """Remove expired keys"""
        now = time.time()
        expired_keys = [
            key for key, expiry in self._expiry.items()
            if expiry <= now
        ]
        for key in expired_keys:
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    def _is_expired(self, key: str) -> bool:
        """Check if a key is expired"""
        if key not in self._expiry:
            return False
        return self._expiry[key] <= time.time()

    def get(self, key: str) -> Optional[Any]:
        """Get value by key, returns None if expired or not found"""
        with self._lock:
            self._maybe_cleanup()
            if key not in self._data or self._is_expired(key):
                return None
            return self._data.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set key-value pair with optional TTL (in seconds)

        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (None = no expiry)

        Returns:
            True on success
        """
        with self._lock:
            self._data[key] = value
            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            elif key in self._expiry:
                del self._expiry[key]
            return True

    def delete(self, key: str) -> bool:
        """Delete a key, returns True if existed"""
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            return existed

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        with self._lock:
            if key not in self._data:
                return False
            if self._is_expired(key):
                self.delete(key)
                return False
            return True

    def keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern (simple * wildcard only)"""
        with self._lock:
            self._maybe_cleanup()

            if pattern == "*":
                return [k for k in self._data.keys() if not self._is_expired(k)]

            # Simple prefix/suffix matching
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in self._data.keys() if k.startswith(prefix) and not self._is_expired(k)]
            elif pattern.startswith("*"):
                suffix = pattern[1:]
                return [k for k in self._data.keys() if k.endswith(suffix) and not self._is_expired(k)]
            else:
                # Exact match
                return [pattern] if pattern in self._data and not self._is_expired(pattern) else []

    def incr(self, key: str, amount: int = 1) -> int:
        """Increment numeric value (atomic)"""
        with self._lock:
            current = self.get(key)
            if current is None:
                current = 0
            new_value = int(current) + amount
            self._data[key] = new_value
            return new_value

    def decr(self, key: str, amount: int = 1) -> int:
        """Decrement numeric value (atomic)"""
        return self.incr(key, -amount)

    def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        with self._lock:
            if key not in self._data:
                self._data[key] = {}
            elif not isinstance(self._data[key], dict):
                self._data[key] = {}
            self._data[key][field] = value
            return True

    def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        with self._lock:
            if key not in self._data or self._is_expired(key):
                return None
            data = self._data.get(key)
            if not isinstance(data, dict):
                return None
            return data.get(field)

    def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        with self._lock:
            if key not in self._data or self._is_expired(key):
                return {}
            data = self._data.get(key)
            if not isinstance(data, dict):
                return {}
            return data.copy()

    def lpush(self, key: str, value: Any) -> int:
        """Push value to left of list"""
        with self._lock:
            if key not in self._data:
                self._data[key] = []
            elif not isinstance(self._data[key], list):
                self._data[key] = []
            self._data[key].insert(0, value)
            return len(self._data[key])

    def rpush(self, key: str, value: Any) -> int:
        """Push value to right of list"""
        with self._lock:
            if key not in self._data:
                self._data[key] = []
            elif not isinstance(self._data[key], list):
                self._data[key] = []
            self._data[key].append(value)
            return len(self._data[key])

    def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """Get range of list"""
        with self._lock:
            if key not in self._data or self._is_expired(key):
                return []
            data = self._data.get(key)
            if not isinstance(data, list):
                return []
            # Redis uses inclusive end, Python uses exclusive
            if end == -1:
                return data[start:]
            return data[start:end + 1]

    def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim list to range"""
        with self._lock:
            if key not in self._data:
                return True
            data = self._data.get(key)
            if not isinstance(data, list):
                return True
            if end == -1:
                self._data[key] = data[start:]
            else:
                self._data[key] = data[start:end + 1]
            return True

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on existing key"""
        with self._lock:
            if key not in self._data:
                return False
            self._expiry[key] = time.time() + seconds
            return True

    def ttl(self, key: str) -> int:
        """Get remaining TTL in seconds (-1 = no expiry, -2 = not found)"""
        with self._lock:
            if key not in self._data:
                return -2
            if key not in self._expiry:
                return -1
            remaining = self._expiry[key] - time.time()
            return max(0, int(remaining))

    def clear(self):
        """Clear all data"""
        with self._lock:
            self._data.clear()
            self._expiry.clear()


class CartStore:
    """
    Shopping cart storage for conversations
    Persists cart items with 1-hour TTL
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or _global_store
        self._ttl = 3600  # 1 hour

    def _key(self, conversation_id: str) -> str:
        return f"cart:{conversation_id}"

    def get_cart(self, conversation_id: str) -> Dict[str, Any]:
        """Get cart for conversation"""
        cart = self._store.get(self._key(conversation_id))
        if cart is None:
            return {"items": [], "total": 0.0, "item_count": 0}
        return cart

    def update_cart(self, conversation_id: str, cart: Dict[str, Any]) -> bool:
        """Update cart for conversation"""
        return self._store.set(self._key(conversation_id), cart, ttl=self._ttl)

    def add_item(
        self,
        conversation_id: str,
        product_id: str,
        name: str,
        price: float,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Add item to cart"""
        cart = self.get_cart(conversation_id)
        items = cart.get("items", [])

        # Check if item already exists
        existing = next((i for i in items if i["product_id"] == product_id), None)
        if existing:
            existing["quantity"] += quantity
            existing["subtotal"] = existing["quantity"] * existing["price"]
        else:
            items.append({
                "product_id": product_id,
                "name": name,
                "price": price,
                "quantity": quantity,
                "subtotal": price * quantity,
            })

        # Recalculate totals
        total = sum(item["subtotal"] for item in items)
        item_count = sum(item["quantity"] for item in items)

        cart = {"items": items, "total": total, "item_count": item_count}
        self.update_cart(conversation_id, cart)
        return cart

    def remove_item(
        self,
        conversation_id: str,
        product_id: str,
        quantity: Optional[int] = None
    ) -> Dict[str, Any]:
        """Remove item from cart (quantity=None removes all)"""
        cart = self.get_cart(conversation_id)
        items = cart.get("items", [])

        existing = next((i for i in items if i["product_id"] == product_id), None)
        if existing:
            if quantity is None or quantity >= existing["quantity"]:
                items.remove(existing)
            else:
                existing["quantity"] -= quantity
                existing["subtotal"] = existing["quantity"] * existing["price"]

        # Recalculate totals
        total = sum(item["subtotal"] for item in items)
        item_count = sum(item["quantity"] for item in items)

        cart = {"items": items, "total": total, "item_count": item_count}
        self.update_cart(conversation_id, cart)
        return cart

    def clear_cart(self, conversation_id: str) -> bool:
        """Clear cart for conversation"""
        return self._store.delete(self._key(conversation_id))


class ConversationStore:
    """
    Conversation message storage
    Keeps last N messages per conversation with TTL
    """

    def __init__(self, store: Optional[MemoryStore] = None, max_messages: int = 50):
        self._store = store or _global_store
        self._max_messages = max_messages
        self._ttl = 7200  # 2 hours

    def _key(self, conversation_id: str) -> str:
        return f"messages:{conversation_id}"

    def _metadata_key(self, conversation_id: str) -> str:
        return f"conv_meta:{conversation_id}"

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Add message to conversation, returns message count"""
        key = self._key(conversation_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        count = self._store.rpush(key, message)
        self._store.expire(key, self._ttl)

        # Trim to max messages
        if count > self._max_messages:
            self._store.ltrim(key, -self._max_messages, -1)

        return count

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for conversation"""
        key = self._key(conversation_id)
        if limit:
            return self._store.lrange(key, -limit, -1)
        return self._store.lrange(key, 0, -1)

    def get_last_message(self, conversation_id: str) -> Optional[Dict]:
        """Get last message in conversation"""
        messages = self.get_messages(conversation_id, limit=1)
        return messages[-1] if messages else None

    def clear(self, conversation_id: str) -> bool:
        """Clear messages for conversation"""
        return self._store.delete(self._key(conversation_id))

    def set_metadata(self, conversation_id: str, key: str, value: Any) -> bool:
        """Set conversation metadata"""
        meta_key = self._metadata_key(conversation_id)
        return self._store.hset(meta_key, key, value)

    def get_metadata(self, conversation_id: str) -> Dict[str, Any]:
        """Get all conversation metadata"""
        meta_key = self._metadata_key(conversation_id)
        return self._store.hgetall(meta_key)


class SessionStore:
    """
    Session storage for user sessions
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or _global_store
        self._ttl = 3600  # 1 hour

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session data"""
        return self._store.hgetall(self._key(session_id)) or {}

    def set_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Set session data"""
        key = self._key(session_id)
        for field, value in data.items():
            self._store.hset(key, field, value)
        self._store.expire(key, self._ttl)
        return True

    def update_field(self, session_id: str, field: str, value: Any) -> bool:
        """Update single session field"""
        key = self._key(session_id)
        self._store.hset(key, field, value)
        self._store.expire(key, self._ttl)
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return self._store.delete(self._key(session_id))


class LockManager:
    """
    Simple distributed lock manager for single-instance deployments
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or _global_store
        self._default_ttl = 10  # 10 seconds

    def _key(self, name: str) -> str:
        return f"lock:{name}"

    def acquire(self, name: str, ttl: Optional[int] = None) -> bool:
        """Acquire lock, returns True if successful"""
        key = self._key(name)
        ttl = ttl or self._default_ttl

        # Simple lock using set-if-not-exists
        if self._store.exists(key):
            return False

        self._store.set(key, time.time(), ttl=ttl)
        return True

    def release(self, name: str) -> bool:
        """Release lock"""
        return self._store.delete(self._key(name))

    def is_locked(self, name: str) -> bool:
        """Check if lock is held"""
        return self._store.exists(self._key(name))


# Global store instance
_global_store = MemoryStore()


def get_store() -> MemoryStore:
    """Get global memory store instance"""
    return _global_store


def get_cart_store() -> CartStore:
    """Get cart store instance"""
    return CartStore(_global_store)


def get_conversation_store() -> ConversationStore:
    """Get conversation store instance"""
    return ConversationStore(_global_store)


def get_session_store() -> SessionStore:
    """Get session store instance"""
    return SessionStore(_global_store)


def get_lock_manager() -> LockManager:
    """Get lock manager instance"""
    return LockManager(_global_store)
