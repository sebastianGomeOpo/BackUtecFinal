"""
Seed coupons collection in MongoDB
"""
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "AgentN")

COUPONS = [
    # Follow-up discount coupons (auto-applied by agent)
    {
        "code": "FOLLOWUP10",
        "description": "Descuento por follow-up - Primera oferta",
        "discount_type": "percentage",
        "discount_value": 10,
        "min_purchase": 100,
        "max_discount": 500,
        "usage_limit": 1000,
        "used_count": 0,
        "is_followup": True,
        "followup_level": 1,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=365)
    },
    {
        "code": "FOLLOWUP15",
        "description": "Descuento por follow-up - Segunda oferta",
        "discount_type": "percentage",
        "discount_value": 15,
        "min_purchase": 100,
        "max_discount": 750,
        "usage_limit": 500,
        "used_count": 0,
        "is_followup": True,
        "followup_level": 2,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=365)
    },
    # General promotional coupons
    {
        "code": "BIENVENIDO10",
        "description": "Descuento de bienvenida para nuevos clientes",
        "discount_type": "percentage",
        "discount_value": 10,
        "min_purchase": 50,
        "max_discount": 200,
        "usage_limit": 5000,
        "used_count": 0,
        "is_followup": False,
        "followup_level": 0,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=365)
    },
    {
        "code": "HOGAR20",
        "description": "20% en artículos del hogar",
        "discount_type": "percentage",
        "discount_value": 20,
        "min_purchase": 500,
        "max_discount": 1000,
        "usage_limit": 200,
        "used_count": 0,
        "is_followup": False,
        "followup_level": 0,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=90)
    },
    {
        "code": "ENVIOGRATIS",
        "description": "Envío gratis en compras mayores a $200",
        "discount_type": "fixed",
        "discount_value": 50,
        "min_purchase": 200,
        "max_discount": 50,
        "usage_limit": 1000,
        "used_count": 0,
        "is_followup": False,
        "followup_level": 0,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=180)
    },
    {
        "code": "FLASH25",
        "description": "Venta flash - 25% de descuento",
        "discount_type": "percentage",
        "discount_value": 25,
        "min_purchase": 300,
        "max_discount": 500,
        "usage_limit": 100,
        "used_count": 0,
        "is_followup": False,
        "followup_level": 0,
        "active": True,
        "expires_at": datetime.utcnow() + timedelta(days=7)
    }
]


async def seed_coupons():
    """Seed coupons collection"""
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]
    
    print("🎟️  Seeding coupons collection...")
    
    # Clear existing coupons
    await db.coupons.delete_many({})
    print("   Cleared existing coupons")
    
    # Insert new coupons
    for coupon in COUPONS:
        coupon["created_at"] = datetime.utcnow()
        coupon["updated_at"] = datetime.utcnow()
        await db.coupons.insert_one(coupon)
        print(f"   ✅ Created coupon: {coupon['code']} ({coupon['discount_value']}% off)")
    
    # Create index for quick lookup
    await db.coupons.create_index("code", unique=True)
    await db.coupons.create_index("is_followup")
    await db.coupons.create_index("active")
    
    print(f"\n✅ Seeded {len(COUPONS)} coupons successfully!")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_coupons())
