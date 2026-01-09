"""
Stock Reservation Service
Manages temporary stock reservations with 15-minute TTL
Uses SQLAlchemy instead of MongoDB
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.sqlite_db import Database
from ..database.models import (
    StockReservationModel, ProductModel, OrderModel, OrderItemModel
)


class StockReservationService:
    """
    Manages temporary stock reservations for cart items.
    Reservations expire after 15 minutes if not confirmed.
    """

    RESERVATION_TTL_MINUTES = 15

    def __init__(self):
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _get_session(self) -> AsyncSession:
        """Get a database session"""
        session_gen = Database.get_session()
        return await anext(session_gen)

    async def start_cleanup_task(self):
        """Start background task to clean up expired reservations"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Background loop to release expired reservations"""
        while True:
            try:
                await self.release_expired_reservations()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Error in reservation cleanup: {e}")
                await asyncio.sleep(60)

    async def reserve_stock(
        self,
        conversation_id: str,
        product_id: str,
        quantity: int,
        user_id: str
    ) -> Dict:
        """
        Reserve stock for a product temporarily.
        """
        session = await self._get_session()
        try:
            # Check available stock
            product_stmt = select(ProductModel).where(ProductModel.id == product_id)
            result = await session.execute(product_stmt)
            product = result.scalar_one_or_none()

            if not product:
                return {"success": False, "error": "Producto no encontrado"}

            total_stock = product.stock or 0

            # Get total reserved for this product (excluding current conversation)
            reserved_stmt = select(func.sum(StockReservationModel.quantity)).where(
                StockReservationModel.product_id == product_id,
                StockReservationModel.conversation_id != conversation_id,
                StockReservationModel.expires_at > datetime.utcnow()
            )
            reserved_result = await session.execute(reserved_stmt)
            total_reserved = reserved_result.scalar() or 0
            available_stock = total_stock - total_reserved

            if quantity > available_stock:
                return {
                    "success": False,
                    "error": f"Stock insuficiente. Disponible: {available_stock}, Solicitado: {quantity}",
                    "available_stock": available_stock
                }

            # Check if reservation already exists
            existing_stmt = select(StockReservationModel).where(
                StockReservationModel.conversation_id == conversation_id,
                StockReservationModel.product_id == product_id
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            expires_at = datetime.utcnow() + timedelta(minutes=self.RESERVATION_TTL_MINUTES)

            if existing:
                # Update existing reservation
                new_quantity = existing.quantity + quantity
                if new_quantity > available_stock + existing.quantity:
                    return {
                        "success": False,
                        "error": "Stock insuficiente para cantidad total",
                        "available_stock": available_stock + existing.quantity
                    }
                existing.quantity = new_quantity
                existing.expires_at = expires_at
                reserved_quantity = new_quantity
            else:
                # Create new reservation
                reservation = StockReservationModel(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    product_id=product_id,
                    quantity=quantity,
                    expires_at=expires_at,
                    created_at=datetime.utcnow()
                )
                session.add(reservation)
                reserved_quantity = quantity

            await session.commit()

            return {
                "success": True,
                "product_id": product_id,
                "product_name": product.name,
                "reserved_quantity": reserved_quantity,
                "expires_at": expires_at.isoformat(),
                "available_stock": available_stock - quantity
            }
        finally:
            await session.close()

    async def get_cart(self, conversation_id: str) -> List[Dict]:
        """Get all reservations (cart items) for a conversation"""
        session = await self._get_session()
        try:
            stmt = select(StockReservationModel).where(
                StockReservationModel.conversation_id == conversation_id,
                StockReservationModel.expires_at > datetime.utcnow()
            )
            result = await session.execute(stmt)
            reservations = result.scalars().all()

            cart_items = []
            for res in reservations:
                # Get product info
                product_stmt = select(ProductModel).where(ProductModel.id == res.product_id)
                product_result = await session.execute(product_stmt)
                product = product_result.scalar_one_or_none()

                if product:
                    cart_items.append({
                        "product_id": res.product_id,
                        "product_name": product.name,
                        "quantity": res.quantity,
                        "price": product.price,
                        "subtotal": product.price * res.quantity,
                        "image_key": product.images[0] if product.images else None,
                        "expires_at": res.expires_at.isoformat()
                    })

            return cart_items
        finally:
            await session.close()

    async def get_cart_total(self, conversation_id: str) -> Dict:
        """Get cart total for a conversation"""
        cart_items = await self.get_cart(conversation_id)
        total = sum(item["subtotal"] for item in cart_items)

        return {
            "items": cart_items,
            "item_count": len(cart_items),
            "total_quantity": sum(item["quantity"] for item in cart_items),
            "total": total
        }

    async def remove_from_cart(
        self,
        conversation_id: str,
        product_id: str,
        quantity: Optional[int] = None
    ) -> Dict:
        """Remove item from cart (release reservation)"""
        session = await self._get_session()
        try:
            stmt = select(StockReservationModel).where(
                StockReservationModel.conversation_id == conversation_id,
                StockReservationModel.product_id == product_id
            )
            result = await session.execute(stmt)
            reservation = result.scalar_one_or_none()

            if not reservation:
                return {"success": False, "error": "Producto no está en el carrito"}

            if quantity is None or quantity >= reservation.quantity:
                # Remove entire reservation
                await session.delete(reservation)
                await session.commit()
                return {
                    "success": True,
                    "message": "Producto eliminado del carrito",
                    "removed_quantity": reservation.quantity
                }
            else:
                # Reduce quantity
                new_quantity = reservation.quantity - quantity
                reservation.quantity = new_quantity
                await session.commit()
                return {
                    "success": True,
                    "message": "Cantidad reducida",
                    "new_quantity": new_quantity,
                    "removed_quantity": quantity
                }
        finally:
            await session.close()

    async def confirm_order(self, conversation_id: str, user_id: str) -> Dict:
        """Confirm order: convert reservations to actual stock deduction"""
        session = await self._get_session()
        try:
            # Get all reservations
            stmt = select(StockReservationModel).where(
                StockReservationModel.conversation_id == conversation_id,
                StockReservationModel.expires_at > datetime.utcnow()
            )
            result = await session.execute(stmt)
            reservations = result.scalars().all()

            if not reservations:
                return {"success": False, "error": "No hay productos en el carrito"}

            order_items = []
            total = 0
            order_id = str(uuid.uuid4())
            order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

            # Process each reservation
            for res in reservations:
                product_stmt = select(ProductModel).where(ProductModel.id == res.product_id)
                product_result = await session.execute(product_stmt)
                product = product_result.scalar_one_or_none()

                if not product:
                    continue

                # Check and deduct stock
                new_stock = product.stock - res.quantity
                if new_stock < 0:
                    return {
                        "success": False,
                        "error": f"Stock insuficiente para {product.name}"
                    }

                product.stock = new_stock
                item_total = product.price * res.quantity

                # Create order item
                order_item = OrderItemModel(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    product_id=res.product_id,
                    quantity=res.quantity,
                    unit_price=product.price,
                    subtotal=item_total,
                    discount=0.0
                )
                session.add(order_item)

                order_items.append({
                    "product_id": res.product_id,
                    "product_name": product.name,
                    "quantity": res.quantity,
                    "unit_price": product.price,
                    "subtotal": item_total
                })
                total += item_total

                # Delete reservation
                await session.delete(res)

            # Create order
            order = OrderModel(
                id=order_id,
                order_number=order_number,
                customer_id=user_id,
                subtotal=total,
                discount=0.0,
                tax=0.0,
                total=total,
                status="confirmed",
                created_at=datetime.utcnow()
            )
            session.add(order)
            await session.commit()

            return {
                "success": True,
                "order_number": order_number,
                "items": order_items,
                "total": total,
                "message": f"Orden {order_number} confirmada exitosamente"
            }
        finally:
            await session.close()

    async def release_expired_reservations(self):
        """Release all expired reservations"""
        session = await self._get_session()
        try:
            stmt = delete(StockReservationModel).where(
                StockReservationModel.expires_at < datetime.utcnow()
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                print(f"Released {result.rowcount} expired reservations")
        finally:
            await session.close()

    async def get_available_stock(self, product_id: str) -> int:
        """Get available stock for a product (total - reserved)"""
        session = await self._get_session()
        try:
            # Get product stock
            product_stmt = select(ProductModel).where(ProductModel.id == product_id)
            result = await session.execute(product_stmt)
            product = result.scalar_one_or_none()

            if not product:
                return 0

            total_stock = product.stock or 0

            # Get total reserved
            reserved_stmt = select(func.sum(StockReservationModel.quantity)).where(
                StockReservationModel.product_id == product_id,
                StockReservationModel.expires_at > datetime.utcnow()
            )
            reserved_result = await session.execute(reserved_stmt)
            total_reserved = reserved_result.scalar() or 0

            return max(0, total_stock - total_reserved)
        finally:
            await session.close()


# Global instance
_stock_service: Optional[StockReservationService] = None


def get_stock_service() -> StockReservationService:
    """Get or create the global stock service instance"""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockReservationService()
    return _stock_service
