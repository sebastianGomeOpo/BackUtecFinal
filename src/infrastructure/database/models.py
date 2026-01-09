"""
SQLAlchemy ORM Models for Local SQLite Database
Replaces MongoDB collections with proper relational schema
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, create_engine, event
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class ProductModel(Base):
    """Product catalog model"""
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    sku = Column(String, nullable=False, unique=True, index=True)
    images = Column(JSON, default=[])  # List of image URLs
    specifications = Column(JSON, default={})  # Product specifications
    meta_data = Column(JSON, default={})  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stock_reservations = relationship("StockReservationModel", back_populates="product")
    order_items = relationship("OrderItemModel", back_populates="product")

    __table_args__ = (
        Index("ix_products_category_name", "category", "name"),
    )


class CustomerModel(Base):
    """Customer profile model"""
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True, index=True)
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    preferences = Column(JSON, default={})  # Customer preferences
    purchase_history = Column(JSON, default=[])  # List of product IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("OrderModel", back_populates="customer")


class OrderItemModel(Base):
    """Individual item in an order"""
    __tablename__ = "order_items"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)

    # Relationships
    order = relationship("OrderModel", back_populates="items")
    product = relationship("ProductModel", back_populates="order_items")


class OrderModel(Base):
    """Order model - confirmed orders"""
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    order_number = Column(String, nullable=False, unique=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    delivery_slot_id = Column(String, ForeignKey("delivery_slots.id"), nullable=True)
    subtotal = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    status = Column(String, default="pending", index=True)  # pending, confirmed, shipped, delivered, cancelled
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("CustomerModel", back_populates="orders")
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")
    delivery_slot = relationship("DeliverySlotModel", back_populates="orders")


class CouponModel(Base):
    """Discount coupon model"""
    __tablename__ = "coupons"

    id = Column(String, primary_key=True)
    code = Column(String, nullable=False, unique=True, index=True)
    discount_type = Column(String, nullable=False)  # "percentage" or "fixed"
    discount_value = Column(Float, nullable=False)
    min_purchase = Column(Float, default=0.0)
    max_uses = Column(Integer, nullable=True)  # None = unlimited
    current_uses = Column(Integer, default=0)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True, index=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeliverySlotModel(Base):
    """Available delivery time slots"""
    __tablename__ = "delivery_slots"

    id = Column(String, primary_key=True)
    date = Column(String, nullable=False, index=True)  # YYYY-MM-DD
    time_start = Column(String, nullable=False)  # HH:MM
    time_end = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    reserved = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    orders = relationship("OrderModel", back_populates="delivery_slot")

    __table_args__ = (
        Index("ix_delivery_slots_date_time", "date", "time_start"),
        UniqueConstraint("date", "time_start", "time_end", name="uq_delivery_slot_time"),
    )


class DistrictModel(Base):
    """Delivery districts"""
    __tablename__ = "districts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)
    delivery_cost = Column(Float, nullable=False)
    min_purchase = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    meta_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class StockReservationModel(Base):
    """Temporary stock reservations (15 min TTL)"""
    __tablename__ = "stock_reservations"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    conversation_id = Column(String, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("ProductModel", back_populates="stock_reservations")

    __table_args__ = (
        Index("ix_stock_reservations_product_conversation", "product_id", "conversation_id"),
    )


class EscalationModel(Base):
    """Escalations requiring human review"""
    __tablename__ = "escalations"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False, unique=True, index=True)
    message = Column(String, nullable=False)
    reason = Column(String, nullable=False)  # reason for escalation
    status = Column(String, default="pending", index=True)  # pending, in_progress, resolved
    assigned_to = Column(String, nullable=True)  # assigned human agent
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_escalations_status_created", "status", "created_at"),
    )


class PlacePostModel(Base):
    """Place posts for recommendation system"""
    __tablename__ = "place_posts"

    id = Column(String, primary_key=True)
    image_url = Column(String, nullable=False)
    title = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String, nullable=False)
    neighborhood = Column(String, nullable=True)
    sponsor = Column(String, default="Coca-Cola Andina")
    tags = Column(JSON, default=[])
    meta_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_place_posts_category", "category"),
        Index("ix_place_posts_location", "latitude", "longitude"),
    )


class ConversationModel(Base):
    """Conversation metadata"""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True, index=True)
    status = Column(String, default="active", index=True)  # active, completed, archived
    stage = Column(String, nullable=True)  # discovery, proposal, optimization, commitment, checkout, completed
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_conversations_user_status", "user_id", "status"),
    )


# ============================================================================
# Enable SQLite WAL mode for better concurrency
# ============================================================================

def configure_sqlite(dbapi_conn, connection_record):
    """Enable WAL mode for SQLite"""
    if dbapi_conn.driver == "pysqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def register_sqlite_pragma(engine):
    """Register SQLite pragma configuration"""
    if "sqlite" in str(engine.url):
        event.listen(engine, "connect", configure_sqlite)
