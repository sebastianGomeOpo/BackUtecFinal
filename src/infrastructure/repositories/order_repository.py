"""
Order repository implementation using SQLAlchemy
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ...domain.entities import Order
from ..database.models import OrderModel
import uuid


class SQLAlchemyOrderRepository:
    """SQLAlchemy implementation of order repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, order_data: dict) -> dict:
        """Create a new order"""
        order_id = str(uuid.uuid4())
        order_model = OrderModel(
            id=order_id,
            order_number=order_data.get("order_number"),
            customer_id=order_data.get("customer_id"),
            delivery_slot_id=order_data.get("delivery_slot_id"),
            subtotal=order_data.get("subtotal", 0.0),
            discount=order_data.get("discount", 0.0),
            tax=order_data.get("tax", 0.0),
            total=order_data.get("total", 0.0),
            status=order_data.get("status", "pending"),
            notes=order_data.get("notes"),
        )
        self.session.add(order_model)
        await self.session.commit()
        return {"id": order_id, **order_data}

    async def get_by_id(self, order_id: str) -> Optional[dict]:
        """Get order by ID"""
        stmt = select(OrderModel).where(OrderModel.id == order_id)
        result = await self.session.execute(stmt)
        order_model = result.scalar_one_or_none()

        if order_model:
            return self._model_to_dict(order_model)
        return None

    async def get_by_customer(self, customer_id: str, limit: int = 50) -> List[dict]:
        """Get orders by customer ID"""
        stmt = select(OrderModel).where(
            OrderModel.customer_id == customer_id
        ).limit(limit)
        result = await self.session.execute(stmt)
        order_models = result.scalars().all()

        return [self._model_to_dict(model) for model in order_models]

    async def update_status(self, order_id: str, status: str) -> bool:
        """Update order status"""
        stmt = update(OrderModel).where(
            OrderModel.id == order_id
        ).values(status=status)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_by_status(self, status: str, limit: int = 50) -> List[dict]:
        """Get orders by status"""
        stmt = select(OrderModel).where(
            OrderModel.status == status
        ).limit(limit)
        result = await self.session.execute(stmt)
        order_models = result.scalars().all()

        return [self._model_to_dict(model) for model in order_models]

    @staticmethod
    def _model_to_dict(model: OrderModel) -> dict:
        """Convert SQLAlchemy model to dictionary"""
        return {
            "id": model.id,
            "order_number": model.order_number,
            "customer_id": model.customer_id,
            "delivery_slot_id": model.delivery_slot_id,
            "subtotal": model.subtotal,
            "discount": model.discount,
            "tax": model.tax,
            "total": model.total,
            "status": model.status,
            "notes": model.notes,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
