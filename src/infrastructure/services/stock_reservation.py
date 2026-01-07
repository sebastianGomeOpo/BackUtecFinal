"""
Stock Reservation Service
Manages temporary stock reservations with 5-minute TTL
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..database.mongodb import MongoDB


class StockReservationService:
    """
    Manages temporary stock reservations for cart items.
    Reservations expire after 5 minutes if not confirmed.
    """
    
    RESERVATION_TTL_MINUTES = 5
    
    def __init__(self):
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _get_db(self) -> AsyncIOMotorDatabase:
        return MongoDB.get_database()
    
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
        
        Args:
            conversation_id: The conversation/cart ID
            product_id: Product to reserve
            quantity: Quantity to reserve
            user_id: User making the reservation
            
        Returns:
            Dict with success status and reservation details
        """
        db = self._get_db()
        
        # Check available stock (total - reserved)
        product = await db.products.find_one({"id": product_id})
        if not product:
            return {"success": False, "error": "Producto no encontrado"}
        
        total_stock = product.get("stock", 0)
        
        # Get total reserved for this product (excluding current conversation)
        reserved = await db.stock_reservations.aggregate([
            {
                "$match": {
                    "product_id": product_id,
                    "conversation_id": {"$ne": conversation_id},
                    "expires_at": {"$gt": datetime.utcnow()}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_reserved": {"$sum": "$quantity"}
                }
            }
        ]).to_list(length=1)
        
        total_reserved = reserved[0]["total_reserved"] if reserved else 0
        available_stock = total_stock - total_reserved
        
        if quantity > available_stock:
            return {
                "success": False,
                "error": f"Stock insuficiente. Disponible: {available_stock}, Solicitado: {quantity}",
                "available_stock": available_stock
            }
        
        # Create or update reservation
        expires_at = datetime.utcnow() + timedelta(minutes=self.RESERVATION_TTL_MINUTES)
        
        # Check if reservation already exists for this conversation and product
        existing = await db.stock_reservations.find_one({
            "conversation_id": conversation_id,
            "product_id": product_id
        })
        
        if existing:
            # Update existing reservation
            new_quantity = existing.get("quantity", 0) + quantity
            if new_quantity > available_stock + existing.get("quantity", 0):
                return {
                    "success": False,
                    "error": f"Stock insuficiente para cantidad total",
                    "available_stock": available_stock + existing.get("quantity", 0)
                }
            
            await db.stock_reservations.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "expires_at": expires_at,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            reserved_quantity = new_quantity
        else:
            # Create new reservation
            await db.stock_reservations.insert_one({
                "conversation_id": conversation_id,
                "product_id": product_id,
                "product_name": product.get("name"),
                "quantity": quantity,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "status": "reserved"
            })
            reserved_quantity = quantity
        
        return {
            "success": True,
            "product_id": product_id,
            "product_name": product.get("name"),
            "reserved_quantity": reserved_quantity,
            "expires_at": expires_at.isoformat(),
            "available_stock": available_stock - quantity
        }
    
    async def get_cart(self, conversation_id: str) -> List[Dict]:
        """Get all reservations (cart items) for a conversation"""
        db = self._get_db()
        
        reservations = await db.stock_reservations.find({
            "conversation_id": conversation_id,
            "expires_at": {"$gt": datetime.utcnow()},
            "status": "reserved"
        }).to_list(length=None)
        
        cart_items = []
        for res in reservations:
            # Get current product info
            product = await db.products.find_one({"id": res["product_id"]})
            if product:
                cart_items.append({
                    "product_id": res["product_id"],
                    "product_name": product.get("name"),
                    "quantity": res["quantity"],
                    "price": product.get("price", 0),
                    "subtotal": product.get("price", 0) * res["quantity"],
                    "image_key": product.get("image_key"),
                    "expires_at": res["expires_at"].isoformat()
                })
        
        return cart_items
    
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
        """
        Remove item from cart (release reservation)
        
        Args:
            conversation_id: The conversation/cart ID
            product_id: Product to remove
            quantity: Quantity to remove (None = remove all)
        """
        db = self._get_db()
        
        reservation = await db.stock_reservations.find_one({
            "conversation_id": conversation_id,
            "product_id": product_id,
            "status": "reserved"
        })
        
        if not reservation:
            return {"success": False, "error": "Producto no está en el carrito"}
        
        if quantity is None or quantity >= reservation["quantity"]:
            # Remove entire reservation
            await db.stock_reservations.delete_one({"_id": reservation["_id"]})
            return {
                "success": True,
                "message": f"Producto eliminado del carrito",
                "removed_quantity": reservation["quantity"]
            }
        else:
            # Reduce quantity
            new_quantity = reservation["quantity"] - quantity
            await db.stock_reservations.update_one(
                {"_id": reservation["_id"]},
                {"$set": {"quantity": new_quantity}}
            )
            return {
                "success": True,
                "message": f"Cantidad reducida",
                "new_quantity": new_quantity,
                "removed_quantity": quantity
            }
    
    async def confirm_order(self, conversation_id: str, user_id: str) -> Dict:
        """
        Confirm order: convert reservations to actual stock deduction
        
        Args:
            conversation_id: The conversation/cart ID
            user_id: User confirming the order
            
        Returns:
            Dict with order details
        """
        db = self._get_db()
        
        # Get all reservations for this conversation
        reservations = await db.stock_reservations.find({
            "conversation_id": conversation_id,
            "status": "reserved",
            "expires_at": {"$gt": datetime.utcnow()}
        }).to_list(length=None)
        
        if not reservations:
            return {"success": False, "error": "No hay productos en el carrito"}
        
        order_items = []
        total = 0
        
        # Process each reservation
        for res in reservations:
            product = await db.products.find_one({"id": res["product_id"]})
            if not product:
                continue
            
            # Deduct stock
            new_stock = product.get("stock", 0) - res["quantity"]
            if new_stock < 0:
                return {
                    "success": False,
                    "error": f"Stock insuficiente para {product.get('name')}"
                }
            
            await db.products.update_one(
                {"id": res["product_id"]},
                {"$set": {"stock": new_stock}}
            )
            
            item_total = product.get("price", 0) * res["quantity"]
            order_items.append({
                "product_id": res["product_id"],
                "product_name": product.get("name"),
                "quantity": res["quantity"],
                "unit_price": product.get("price", 0),
                "subtotal": item_total
            })
            total += item_total
            
            # Mark reservation as confirmed
            await db.stock_reservations.update_one(
                {"_id": res["_id"]},
                {"$set": {"status": "confirmed", "confirmed_at": datetime.utcnow()}}
            )
        
        # Create order with unique order_number
        import uuid
        order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        order = {
            "order_number": order_number,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "items": order_items,
            "total": total,
            "status": "confirmed",
            "created_at": datetime.utcnow()
        }
        
        await db.orders.insert_one(order)
        
        return {
            "success": True,
            "order_number": order_number,
            "items": order_items,
            "total": total,
            "message": f"Orden {order_number} confirmada exitosamente"
        }
    
    async def release_expired_reservations(self):
        """Release all expired reservations"""
        db = self._get_db()
        
        result = await db.stock_reservations.delete_many({
            "expires_at": {"$lt": datetime.utcnow()},
            "status": "reserved"
        })
        
        if result.deleted_count > 0:
            print(f"🔄 Released {result.deleted_count} expired reservations")
    
    async def get_available_stock(self, product_id: str) -> int:
        """Get available stock for a product (total - reserved)"""
        db = self._get_db()
        
        product = await db.products.find_one({"id": product_id})
        if not product:
            return 0
        
        total_stock = product.get("stock", 0)
        
        # Get total reserved
        reserved = await db.stock_reservations.aggregate([
            {
                "$match": {
                    "product_id": product_id,
                    "expires_at": {"$gt": datetime.utcnow()},
                    "status": "reserved"
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_reserved": {"$sum": "$quantity"}
                }
            }
        ]).to_list(length=1)
        
        total_reserved = reserved[0]["total_reserved"] if reserved else 0
        return max(0, total_stock - total_reserved)


# Global instance
_stock_service: Optional[StockReservationService] = None


def get_stock_service() -> StockReservationService:
    """Get or create the global stock service instance"""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockReservationService()
    return _stock_service
