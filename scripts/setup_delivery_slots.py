"""
Script to setup delivery slots and update products with SKUs in MongoDB
"""
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "AgentN")


async def setup_delivery_slots():
    """Create delivery slots for the next 7 days"""
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    
    # Drop existing collection
    await db.delivery_slots.drop()
    
    # Create delivery slots for next 7 days
    slots = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    time_slots = [
        {"start": "09:00", "end": "12:00", "label": "Mañana (9:00 - 12:00)"},
        {"start": "12:00", "end": "15:00", "label": "Mediodía (12:00 - 15:00)"},
        {"start": "15:00", "end": "18:00", "label": "Tarde (15:00 - 18:00)"},
        {"start": "18:00", "end": "21:00", "label": "Noche (18:00 - 21:00)"},
    ]
    
    for day_offset in range(1, 8):  # Next 7 days (not today)
        date = today + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")
        day_name = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][date.weekday()]
        
        # Skip Sundays or limit slots
        if date.weekday() == 6:  # Sunday
            available_slots = time_slots[:2]  # Only morning slots on Sunday
        else:
            available_slots = time_slots
        
        for slot in available_slots:
            slots.append({
                "date": date_str,
                "day_name": day_name,
                "time_start": slot["start"],
                "time_end": slot["end"],
                "label": f"{day_name} {date.strftime('%d/%m')} - {slot['label']}",
                "available": True,
                "max_orders": 10,
                "current_orders": 0,
                "created_at": datetime.utcnow()
            })
    
    if slots:
        await db.delivery_slots.insert_many(slots)
        print(f"✅ Created {len(slots)} delivery slots")
    
    # Create index
    await db.delivery_slots.create_index([("date", 1), ("time_start", 1)])
    await db.delivery_slots.create_index([("available", 1)])
    
    # List created slots
    print("\n📅 Delivery Slots Created:")
    async for slot in db.delivery_slots.find().sort([("date", 1), ("time_start", 1)]):
        print(f"  - {slot['label']}")
    
    client.close()


async def setup_orders_collection():
    """Setup orders collection with proper indexes"""
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    
    # Create indexes for orders collection
    await db.orders.create_index([("order_number", 1)], unique=True)
    await db.orders.create_index([("conversation_id", 1)])
    await db.orders.create_index([("customer.email", 1)])
    await db.orders.create_index([("customer.phone", 1)])
    await db.orders.create_index([("status", 1)])
    await db.orders.create_index([("created_at", -1)])
    
    print("✅ Orders collection indexes created")
    
    client.close()


async def main():
    print("🚀 Setting up delivery slots and orders collection...\n")
    await setup_delivery_slots()
    print()
    await setup_orders_collection()
    print("\n✅ Setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
