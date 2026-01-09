"""
MongoDB Compatibility Shim

Provides MongoDB-like interface backed by SQLite/SQLAlchemy.
This allows existing code to work without modification while using local SQLite.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .sqlite_db import Database
from .models import (
    OrderModel, OrderItemModel, CustomerModel, ConversationModel,
    ProductModel, CouponModel, DeliverySlotModel, DistrictModel,
    EscalationModel, StockReservationModel
)


class MongoCollection:
    """Simulates a MongoDB collection using SQLAlchemy"""

    def __init__(self, model_class, session_factory):
        self.model_class = model_class
        self.session_factory = session_factory

    async def _get_session(self) -> AsyncSession:
        """Get a database session"""
        session_gen = self.session_factory()
        return await anext(session_gen)

    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Dict]:
        """Find a single document matching the filter"""
        session = await self._get_session()
        try:
            # Build query from filter
            stmt = select(self.model_class)
            for key, value in filter_dict.items():
                # Handle special MongoDB fields
                if key == "_id":
                    key = "id"
                if key == "order_id":
                    # Check if model has order_number or id
                    if hasattr(self.model_class, "order_number"):
                        stmt = stmt.where(self.model_class.order_number == value)
                    else:
                        stmt = stmt.where(self.model_class.id == value)
                    continue
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                return self._model_to_dict(row)
            return None
        finally:
            await session.close()

    async def find(self, filter_dict: Dict[str, Any] = None, limit: int = 100) -> List[Dict]:
        """Find documents matching the filter"""
        session = await self._get_session()
        try:
            stmt = select(self.model_class)

            if filter_dict:
                for key, value in filter_dict.items():
                    if key == "_id":
                        key = "id"
                    if hasattr(self.model_class, key):
                        stmt = stmt.where(getattr(self.model_class, key) == value)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            return [self._model_to_dict(row) for row in rows]
        finally:
            await session.close()

    async def insert_one(self, document: Dict[str, Any]) -> Dict:
        """Insert a single document"""
        session = await self._get_session()
        try:
            # Generate ID if not provided
            if "_id" not in document and "id" not in document:
                document["id"] = str(uuid.uuid4())
            elif "_id" in document:
                document["id"] = document.pop("_id")

            # Create model instance
            model_data = self._dict_to_model_data(document)
            instance = self.model_class(**model_data)
            session.add(instance)
            await session.commit()

            return {"inserted_id": document.get("id")}
        finally:
            await session.close()

    async def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict:
        """Update a single document"""
        session = await self._get_session()
        try:
            # Handle $set operator
            if "$set" in update_dict:
                update_values = update_dict["$set"]
            else:
                update_values = update_dict

            # Build update statement
            stmt = update(self.model_class)

            for key, value in filter_dict.items():
                if key == "_id":
                    key = "id"
                if key == "order_id" and hasattr(self.model_class, "order_number"):
                    stmt = stmt.where(self.model_class.order_number == value)
                    continue
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)

            # Set update values
            clean_values = {}
            for key, value in update_values.items():
                if key == "_id":
                    continue
                if hasattr(self.model_class, key):
                    clean_values[key] = value

            if clean_values:
                stmt = stmt.values(**clean_values)
                result = await session.execute(stmt)
                await session.commit()
                return {"modified_count": result.rowcount}

            return {"modified_count": 0}
        finally:
            await session.close()

    async def delete_one(self, filter_dict: Dict[str, Any]) -> Dict:
        """Delete a single document"""
        session = await self._get_session()
        try:
            stmt = delete(self.model_class)

            for key, value in filter_dict.items():
                if key == "_id":
                    key = "id"
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)

            result = await session.execute(stmt)
            await session.commit()
            return {"deleted_count": result.rowcount}
        finally:
            await session.close()

    async def count_documents(self, filter_dict: Dict[str, Any] = None) -> int:
        """Count documents matching the filter"""
        docs = await self.find(filter_dict)
        return len(docs)

    def _model_to_dict(self, model) -> Dict:
        """Convert SQLAlchemy model to dictionary"""
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value

        # Add MongoDB-style _id
        if "id" in result:
            result["_id"] = result["id"]

        # Special handling for orders - include items
        if hasattr(model, "items") and model.items:
            result["items"] = []
            for item in model.items:
                item_dict = {
                    "product_id": item.product_id,
                    "name": item.product.name if item.product else "Unknown",
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.subtotal
                }
                result["items"].append(item_dict)

        # Map order_number to order_id for compatibility
        if hasattr(model, "order_number"):
            result["order_id"] = model.order_number

        return result

    def _dict_to_model_data(self, document: Dict) -> Dict:
        """Convert document dictionary to model-compatible data"""
        result = {}
        for key, value in document.items():
            if key == "_id":
                result["id"] = value
            elif key == "order_id" and hasattr(self.model_class, "order_number"):
                result["order_number"] = value
            elif hasattr(self.model_class, key):
                result[key] = value
        return result


class MongoDatabase:
    """Simulates a MongoDB database using SQLAlchemy"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

        # Map collection names to models
        self._collections = {
            "orders": OrderModel,
            "customers": CustomerModel,
            "conversations": ConversationModel,
            "products": ProductModel,
            "coupons": CouponModel,
            "delivery_slots": DeliverySlotModel,
            "districts": DistrictModel,
            "escalations": EscalationModel,
            "stock_reservations": StockReservationModel,
        }

    def __getattr__(self, name: str) -> MongoCollection:
        """Get collection by name (MongoDB-style access)"""
        if name.startswith("_"):
            raise AttributeError(name)

        model_class = self._collections.get(name)
        if model_class:
            return MongoCollection(model_class, self.session_factory)

        # Return a dummy collection for unknown collections
        # This prevents errors when code tries to access collections that don't exist
        return MongoCollection(ConversationModel, self.session_factory)

    def get_collection(self, name: str) -> MongoCollection:
        """Get collection by name (explicit method)"""
        return getattr(self, name)


class MongoDB:
    """MongoDB compatibility layer using SQLite"""

    _database: Optional[MongoDatabase] = None

    @classmethod
    def get_database(cls) -> MongoDatabase:
        """Get the MongoDB-compatible database instance"""
        if cls._database is None:
            cls._database = MongoDatabase(Database.get_session)
        return cls._database

    @classmethod
    async def connect(cls):
        """Connect to database (delegates to SQLite)"""
        await Database.connect()

    @classmethod
    async def disconnect(cls):
        """Disconnect from database"""
        await Database.disconnect()
        cls._database = None

    @classmethod
    def is_connected(cls) -> bool:
        """Check if database is connected"""
        return Database._engine is not None
