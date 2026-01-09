"""
Coupon repository implementation using SQLAlchemy
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from ..database.models import CouponModel


class SQLAlchemyCouponRepository:
    """SQLAlchemy implementation of coupon repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Optional[dict]:
        """Get coupon by code"""
        stmt = select(CouponModel).where(CouponModel.code == code)
        result = await self.session.execute(stmt)
        coupon_model = result.scalar_one_or_none()

        if coupon_model:
            return self._model_to_dict(coupon_model)
        return None

    async def validate(self, code: str, purchase_amount: float) -> bool:
        """Validate coupon (active, not expired, not exceeded max uses, min purchase met)"""
        coupon = await self.get_by_code(code)
        if not coupon:
            return False

        # Check if active
        if not coupon["active"]:
            return False

        # Check if expired
        if coupon["valid_until"] and coupon["valid_until"] < datetime.utcnow():
            return False

        # Check if max uses exceeded
        if coupon["max_uses"] and coupon["current_uses"] >= coupon["max_uses"]:
            return False

        # Check minimum purchase
        if coupon["min_purchase"] and purchase_amount < coupon["min_purchase"]:
            return False

        return True

    async def increment_uses(self, code: str) -> bool:
        """Increment coupon usage count"""
        stmt = update(CouponModel).where(
            CouponModel.code == code
        ).values(current_uses=CouponModel.current_uses + 1)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def create(self, coupon_data: dict) -> dict:
        """Create a new coupon"""
        coupon_model = CouponModel(
            id=coupon_data.get("id"),
            code=coupon_data.get("code"),
            discount_type=coupon_data.get("discount_type"),
            discount_value=coupon_data.get("discount_value"),
            min_purchase=coupon_data.get("min_purchase", 0.0),
            max_uses=coupon_data.get("max_uses"),
            valid_until=coupon_data.get("valid_until"),
            active=coupon_data.get("active", True),
        )
        self.session.add(coupon_model)
        await self.session.commit()
        return self._model_to_dict(coupon_model)

    @staticmethod
    def _model_to_dict(model: CouponModel) -> dict:
        """Convert SQLAlchemy model to dictionary"""
        return {
            "id": model.id,
            "code": model.code,
            "discount_type": model.discount_type,
            "discount_value": model.discount_value,
            "min_purchase": model.min_purchase,
            "max_uses": model.max_uses,
            "current_uses": model.current_uses,
            "valid_from": model.valid_from,
            "valid_until": model.valid_until,
            "active": model.active,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
