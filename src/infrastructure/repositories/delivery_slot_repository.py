"""
Delivery slot repository implementation using SQLAlchemy
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from datetime import datetime, timedelta
from ..database.models import DeliverySlotModel
import uuid


class SQLAlchemyDeliverySlotRepository:
    """SQLAlchemy implementation of delivery slot repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, slot_data: dict) -> dict:
        """Create a new delivery slot"""
        slot_id = str(uuid.uuid4())
        slot_model = DeliverySlotModel(
            id=slot_id,
            date=slot_data.get("date"),  # YYYY-MM-DD
            time_start=slot_data.get("time_start"),  # HH:MM
            time_end=slot_data.get("time_end"),
            capacity=slot_data.get("capacity", 10),
            reserved=slot_data.get("reserved", 0),
            active=slot_data.get("active", True),
        )
        self.session.add(slot_model)
        await self.session.commit()
        return self._model_to_dict(slot_model)

    async def get_available_slots(
        self,
        date: str,
        limit: int = 10
    ) -> List[dict]:
        """Get available slots for a specific date"""
        stmt = select(DeliverySlotModel).where(
            and_(
                DeliverySlotModel.date == date,
                DeliverySlotModel.active == True,
                DeliverySlotModel.reserved < DeliverySlotModel.capacity,
            )
        ).limit(limit)

        result = await self.session.execute(stmt)
        slot_models = result.scalars().all()

        return [self._model_to_dict(model) for model in slot_models]

    async def reserve_slot(self, slot_id: str, quantity: int = 1) -> bool:
        """Reserve capacity in a delivery slot"""
        # Check if there's capacity
        stmt = select(DeliverySlotModel).where(DeliverySlotModel.id == slot_id)
        result = await self.session.execute(stmt)
        slot_model = result.scalar_one_or_none()

        if not slot_model:
            return False

        if slot_model.reserved + quantity > slot_model.capacity:
            return False

        # Reserve
        stmt = update(DeliverySlotModel).where(
            DeliverySlotModel.id == slot_id
        ).values(reserved=DeliverySlotModel.reserved + quantity)

        await self.session.execute(stmt)
        await self.session.commit()
        return True

    async def release_slot(self, slot_id: str, quantity: int = 1) -> bool:
        """Release reserved capacity in a delivery slot"""
        stmt = update(DeliverySlotModel).where(
            DeliverySlotModel.id == slot_id
        ).values(reserved=DeliverySlotModel.reserved - quantity)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_by_id(self, slot_id: str) -> Optional[dict]:
        """Get delivery slot by ID"""
        stmt = select(DeliverySlotModel).where(DeliverySlotModel.id == slot_id)
        result = await self.session.execute(stmt)
        slot_model = result.scalar_one_or_none()

        if slot_model:
            return self._model_to_dict(slot_model)
        return None

    async def cleanup_expired_slots(self, days_in_past: int = 1) -> int:
        """Delete delivery slots from the past (cleanup)"""
        past_date = (datetime.utcnow() - timedelta(days=days_in_past)).strftime("%Y-%m-%d")

        stmt = select(DeliverySlotModel).where(DeliverySlotModel.date < past_date)
        result = await self.session.execute(stmt)
        slots_to_delete = result.scalars().all()

        for slot in slots_to_delete:
            await self.session.delete(slot)

        await self.session.commit()
        return len(slots_to_delete)

    @staticmethod
    def _model_to_dict(model: DeliverySlotModel) -> dict:
        """Convert SQLAlchemy model to dictionary"""
        return {
            "id": model.id,
            "date": model.date,
            "time_start": model.time_start,
            "time_end": model.time_end,
            "capacity": model.capacity,
            "reserved": model.reserved,
            "available": model.capacity - model.reserved,
            "active": model.active,
            "created_at": model.created_at,
        }
