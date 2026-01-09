"""
MongoDB Compatibility Layer
Provides a MongoDB-like interface backed by SQLite (SQLAlchemy)
This is a compatibility layer to ease migration from MongoDB to SQLite.

IMPORTANT: This is a shim layer. Data is actually stored in SQLite.
Do NOT use this for new code - use the repositories or Database class directly.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from .sqlite_db import Database
from .models import (
    ConversationModel,
    OrderModel,
    CustomerModel,
    EscalationModel,
    ProductModel,
    CouponModel,
    DeliverySlotModel
)


class MongoCollection:
    """Mock MongoDB collection backed by SQLAlchemy"""

    def __init__(self, name: str, model_class=None):
        self.name = name
        self.model_class = model_class
        self._session: Optional[AsyncSession] = None

    async def _get_session(self) -> AsyncSession:
        """Get a session"""
        if self._session is None:
            raise RuntimeError("MongoDB session not initialized")
        return self._session

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find one document"""
        try:
            if self._session is None:
                async with Database.async_session_maker() as session:
                    return await self._find_one_impl(session, query)
            return await self._find_one_impl(self._session, query)
        except Exception as e:
            print(f"[MongoDB] Error in find_one: {e}")
            return None

    async def _find_one_impl(self, session: AsyncSession, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Implementation of find_one"""
        if not self.model_class:
            return None

        # Build query from dict
        stmt = select(self.model_class)

        # Apply simple filters (key = value)
        for key, value in query.items():
            if hasattr(self.model_class, key):
                col = getattr(self.model_class, key)
                stmt = stmt.where(col == value)

        result = await session.execute(stmt)
        model_obj = result.scalar_one_or_none()

        if model_obj:
            return self._model_to_dict(model_obj)
        return None

    async def find(self, query: Dict[str, Any] = None):
        """Find multiple documents - returns an async iterator"""
        if query is None:
            query = {}

        async def _iterator():
            try:
                if self._session is None:
                    async with Database.async_session_maker() as session:
                        async for doc in self._find_impl(session, query):
                            yield doc
                else:
                    async for doc in self._find_impl(self._session, query):
                        yield doc
            except Exception as e:
                print(f"[MongoDB] Error in find: {e}")

        return _iterator()

    async def _find_impl(self, session: AsyncSession, query: Dict[str, Any]):
        """Implementation of find"""
        if not self.model_class:
            return

        stmt = select(self.model_class)

        for key, value in query.items():
            if hasattr(self.model_class, key):
                col = getattr(self.model_class, key)
                stmt = stmt.where(col == value)

        result = await session.execute(stmt)
        for model_obj in result.scalars():
            yield self._model_to_dict(model_obj)

    async def insert_one(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one document"""
        try:
            if self._session is None:
                async with Database.async_session_maker() as session:
                    return await self._insert_one_impl(session, document)
            return await self._insert_one_impl(self._session, document)
        except Exception as e:
            print(f"[MongoDB] Error in insert_one: {e}")
            return {"_id": None}

    async def _insert_one_impl(self, session: AsyncSession, document: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of insert_one"""
        if not self.model_class:
            return {"_id": None}

        try:
            model_obj = self.model_class(**document)
            session.add(model_obj)
            await session.flush()
            return {"_id": getattr(model_obj, "id", None)}
        except Exception as e:
            print(f"[MongoDB] Error creating model: {e}")
            return {"_id": None}

    async def update_one(self, query: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Update one document"""
        try:
            if self._session is None:
                async with Database.async_session_maker() as session:
                    return await self._update_one_impl(session, query, update_dict)
            return await self._update_one_impl(self._session, query, update_dict)
        except Exception as e:
            print(f"[MongoDB] Error in update_one: {e}")
            return {"matched_count": 0, "modified_count": 0}

    async def _update_one_impl(self, session: AsyncSession, query: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of update_one"""
        if not self.model_class:
            return {"matched_count": 0, "modified_count": 0}

        try:
            stmt = select(self.model_class)
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    col = getattr(self.model_class, key)
                    stmt = stmt.where(col == value)

            result = await session.execute(stmt)
            model_obj = result.scalar_one_or_none()

            if model_obj:
                # Handle MongoDB $set operator
                data_to_update = update_dict.get("$set", update_dict)
                for key, value in data_to_update.items():
                    if hasattr(model_obj, key):
                        setattr(model_obj, key, value)

                await session.flush()
                return {"matched_count": 1, "modified_count": 1}

            return {"matched_count": 0, "modified_count": 0}
        except Exception as e:
            print(f"[MongoDB] Error updating: {e}")
            return {"matched_count": 0, "modified_count": 0}

    async def delete_one(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Delete one document"""
        try:
            if self._session is None:
                async with Database.async_session_maker() as session:
                    return await self._delete_one_impl(session, query)
            return await self._delete_one_impl(self._session, query)
        except Exception as e:
            print(f"[MongoDB] Error in delete_one: {e}")
            return {"deleted_count": 0}

    async def _delete_one_impl(self, session: AsyncSession, query: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of delete_one"""
        if not self.model_class:
            return {"deleted_count": 0}

        try:
            stmt = delete(self.model_class)
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    col = getattr(self.model_class, key)
                    stmt = stmt.where(col == value)

            result = await session.execute(stmt)
            await session.flush()
            return {"deleted_count": result.rowcount}
        except Exception as e:
            print(f"[MongoDB] Error deleting: {e}")
            return {"deleted_count": 0}

    async def count_documents(self, query: Dict[str, Any] = None) -> int:
        """Count documents"""
        try:
            if query is None:
                query = {}

            if self._session is None:
                async with Database.async_session_maker() as session:
                    return await self._count_impl(session, query)
            return await self._count_impl(self._session, query)
        except Exception as e:
            print(f"[MongoDB] Error in count_documents: {e}")
            return 0

    async def _count_impl(self, session: AsyncSession, query: Dict[str, Any]) -> int:
        """Implementation of count_documents"""
        if not self.model_class:
            return 0

        try:
            stmt = select(self.model_class)
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    col = getattr(self.model_class, key)
                    stmt = stmt.where(col == value)

            result = await session.execute(stmt)
            return len(result.scalars().all())
        except Exception as e:
            print(f"[MongoDB] Error counting: {e}")
            return 0

    def sort(self, field: str, direction: int = 1):
        """Mock sort (returns self for chaining)"""
        return self

    def skip(self, count: int):
        """Mock skip (returns self for chaining)"""
        return self

    def limit(self, count: int):
        """Mock limit (returns self for chaining)"""
        return self

    @staticmethod
    def _model_to_dict(model_obj) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dict"""
        result = {}
        for column in model_obj.__table__.columns:
            result[column.name] = getattr(model_obj, column.name)
        return result


class MongoDatabase:
    """Mock MongoDB database backed by SQLite"""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session
        self.conversations = MongoCollection("conversations", ConversationModel)
        self.orders = MongoCollection("orders", OrderModel)
        self.customers = MongoCollection("customers", CustomerModel)
        self.escalations = MongoCollection("escalations", EscalationModel)
        self.products = MongoCollection("products", ProductModel)
        self.coupons = MongoCollection("coupons", CouponModel)
        self.delivery_slots = MongoCollection("delivery_slots", DeliverySlotModel)

        # Collections that are not directly mapped (for compatibility)
        self.conversations_history = MongoCollection("conversations_history", None)
        self.conversation_messages = MongoCollection("conversation_messages", None)
        self.cart_coupons = MongoCollection("cart_coupons", None)
        self.cart_items = MongoCollection("cart_items", None)

        # Set session for all collections
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, MongoCollection):
                attr._session = self._session

    async def create_session(self):
        """Initialize session"""
        self._session = None  # Use Database.async_session_maker
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, MongoCollection):
                attr._session = self._session


class MongoDB:
    """Singleton MongoDB compatibility layer"""

    _instance: Optional[MongoDatabase] = None

    @classmethod
    def get_database(cls) -> MongoDatabase:
        """Get MongoDB instance"""
        if cls._instance is None:
            cls._instance = MongoDatabase()
        return cls._instance

    @classmethod
    async def connect(cls):
        """Connect (compatibility method)"""
        await Database.connect()

    @classmethod
    async def disconnect(cls):
        """Disconnect (compatibility method)"""
        await Database.disconnect()


# Backward compatibility
def get_mongodb_instance() -> MongoDatabase:
    """Get MongoDB instance"""
    return MongoDB.get_database()
