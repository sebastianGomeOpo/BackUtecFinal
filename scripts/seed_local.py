#!/usr/bin/env python3
"""
Seed Local Database Script
Populates SQLite and ChromaDB with sample data for testing
Includes: Products, Coupons, Delivery Slots, Districts

Run with: python -m scripts.seed_local (from project root)
Or: python scripts/seed_local.py (from project root)
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from src.infrastructure.database.sqlite_db import Database
from src.infrastructure.vectorstore.chroma_store import ChromaStore
from src.config import settings


# =============================================================================
# SAMPLE DATA
# =============================================================================

SAMPLE_PRODUCTS = [
    {
        "id": "prod-001",
        "name": "Sofa Moderno Gris",
        "description": "Sofa de 3 cuerpos tapizado en tela gris, ideal para sala de estar moderna. Estructura de madera y patas metalicas.",
        "category": "Muebles",
        "price": 899.99,
        "stock": 15,
        "sku": "SOFA-MOD-001",
        "specifications": {"color": "Gris", "material": "Tela", "dimensiones": "220x90x85cm"}
    },
    {
        "id": "prod-002",
        "name": "Mesa de Centro Madera",
        "description": "Mesa de centro rectangular en madera de roble con acabado natural. Perfecta para complementar tu sala.",
        "category": "Muebles",
        "price": 299.99,
        "stock": 25,
        "sku": "MESA-CEN-002",
        "specifications": {"color": "Natural", "material": "Roble", "dimensiones": "120x60x45cm"}
    },
    {
        "id": "prod-003",
        "name": "Lampara de Pie LED",
        "description": "Lampara de pie moderna con luz LED regulable. Diseno minimalista en metal negro mate.",
        "category": "Iluminacion",
        "price": 149.99,
        "stock": 40,
        "sku": "LAMP-PIE-003",
        "specifications": {"color": "Negro", "potencia": "15W", "altura": "165cm"}
    },
    {
        "id": "prod-004",
        "name": "Silla de Oficina Ergonomica",
        "description": "Silla ergonomica con soporte lumbar ajustable, reposabrazos y ruedas. Ideal para trabajo prolongado.",
        "category": "Oficina",
        "price": 449.99,
        "stock": 20,
        "sku": "SILLA-ERG-004",
        "specifications": {"color": "Negro", "material": "Malla", "ajuste_altura": "Si"}
    },
    {
        "id": "prod-005",
        "name": "Estante Flotante Blanco",
        "description": "Set de 3 estantes flotantes en MDF blanco. Facil instalacion, incluye herrajes.",
        "category": "Decoracion",
        "price": 79.99,
        "stock": 50,
        "sku": "EST-FLOT-005",
        "specifications": {"color": "Blanco", "cantidad": "3 unidades", "largo": "60cm cada uno"}
    },
    {
        "id": "prod-006",
        "name": "Cama Queen Size",
        "description": "Cama matrimonial queen size con cabecera tapizada. Estructura solida de madera.",
        "category": "Dormitorio",
        "price": 699.99,
        "stock": 10,
        "sku": "CAMA-QUE-006",
        "specifications": {"tamano": "Queen", "color": "Beige", "material": "Madera y tela"}
    },
    {
        "id": "prod-007",
        "name": "Espejo Decorativo Redondo",
        "description": "Espejo redondo con marco dorado. Diametro 80cm, ideal para entrada o sala.",
        "category": "Decoracion",
        "price": 189.99,
        "stock": 30,
        "sku": "ESP-RED-007",
        "specifications": {"forma": "Redondo", "diametro": "80cm", "marco": "Dorado"}
    },
    {
        "id": "prod-008",
        "name": "Escritorio Minimalista",
        "description": "Escritorio de trabajo estilo nordico con cajon. Superficie amplia para computadora y accesorios.",
        "category": "Oficina",
        "price": 349.99,
        "stock": 18,
        "sku": "ESC-MIN-008",
        "specifications": {"color": "Blanco/Madera", "dimensiones": "120x60x75cm", "cajones": "1"}
    },
    {
        "id": "prod-009",
        "name": "Alfombra Shaggy Grande",
        "description": "Alfombra de pelo largo super suave. Color gris claro, perfecta para dormitorio o sala.",
        "category": "Decoracion",
        "price": 199.99,
        "stock": 22,
        "sku": "ALF-SHA-009",
        "specifications": {"tamano": "200x300cm", "material": "Poliester", "color": "Gris claro"}
    },
    {
        "id": "prod-010",
        "name": "Comoda 6 Cajones",
        "description": "Comoda amplia con 6 cajones para almacenamiento. Acabado en madera oscura.",
        "category": "Dormitorio",
        "price": 549.99,
        "stock": 12,
        "sku": "COM-6CA-010",
        "specifications": {"cajones": "6", "color": "Madera oscura", "dimensiones": "140x45x85cm"}
    },
    {
        "id": "prod-011",
        "name": "Televisor Smart TV 55 pulgadas",
        "description": "Smart TV 4K UHD de 55 pulgadas con sistema operativo integrado. HDR, WiFi y Bluetooth.",
        "category": "Electronica",
        "price": 599.99,
        "stock": 8,
        "sku": "TV-55-011",
        "specifications": {"tamano": "55 pulgadas", "resolucion": "4K UHD", "smart": "Si"}
    },
    {
        "id": "prod-012",
        "name": "Refrigeradora No Frost",
        "description": "Refrigeradora de 400 litros con tecnologia No Frost. Dispensador de agua y hielo.",
        "category": "Electrodomesticos",
        "price": 899.99,
        "stock": 5,
        "sku": "REF-NF-012",
        "specifications": {"capacidad": "400L", "tipo": "No Frost", "color": "Acero inoxidable"}
    },
]

SAMPLE_COUPONS = [
    {
        "id": "coup-001",
        "code": "BIENVENIDO10",
        "discount_type": "percentage",
        "discount_value": 10.0,
        "min_purchase": 100.0,
        "max_uses": 100,
        "current_uses": 0,
        "valid_until": datetime.utcnow() + timedelta(days=30),
        "active": True
    },
    {
        "id": "coup-002",
        "code": "ENVIOGRATIS",
        "discount_type": "fixed",
        "discount_value": 15.0,
        "min_purchase": 200.0,
        "max_uses": 50,
        "current_uses": 0,
        "valid_until": datetime.utcnow() + timedelta(days=15),
        "active": True
    },
    {
        "id": "coup-003",
        "code": "DESCUENTO20",
        "discount_type": "percentage",
        "discount_value": 20.0,
        "min_purchase": 500.0,
        "max_uses": 20,
        "current_uses": 0,
        "valid_until": datetime.utcnow() + timedelta(days=7),
        "active": True
    },
    {
        "id": "coup-004",
        "code": "VERANO2024",
        "discount_type": "percentage",
        "discount_value": 15.0,
        "min_purchase": 150.0,
        "max_uses": None,  # Unlimited
        "current_uses": 0,
        "valid_until": datetime.utcnow() + timedelta(days=60),
        "active": True
    },
]

SAMPLE_DISTRICTS = [
    {"id": "dist-001", "name": "Miraflores", "delivery_cost": 10.0, "min_purchase": 50.0},
    {"id": "dist-002", "name": "San Isidro", "delivery_cost": 10.0, "min_purchase": 50.0},
    {"id": "dist-003", "name": "Surco", "delivery_cost": 12.0, "min_purchase": 50.0},
    {"id": "dist-004", "name": "La Molina", "delivery_cost": 15.0, "min_purchase": 100.0},
    {"id": "dist-005", "name": "San Borja", "delivery_cost": 10.0, "min_purchase": 50.0},
    {"id": "dist-006", "name": "Barranco", "delivery_cost": 12.0, "min_purchase": 50.0},
    {"id": "dist-007", "name": "Jesus Maria", "delivery_cost": 12.0, "min_purchase": 50.0},
    {"id": "dist-008", "name": "Lince", "delivery_cost": 12.0, "min_purchase": 50.0},
    {"id": "dist-009", "name": "Magdalena", "delivery_cost": 12.0, "min_purchase": 50.0},
    {"id": "dist-010", "name": "San Miguel", "delivery_cost": 15.0, "min_purchase": 75.0},
]


def generate_delivery_slots():
    """Generate delivery slots for the next 7 days"""
    slots = []
    base_date = datetime.utcnow().date()

    time_ranges = [
        ("09:00", "12:00"),
        ("12:00", "15:00"),
        ("15:00", "18:00"),
        ("18:00", "21:00"),
    ]

    for day_offset in range(7):
        slot_date = base_date + timedelta(days=day_offset)
        date_str = slot_date.strftime("%Y-%m-%d")

        for time_start, time_end in time_ranges:
            slots.append({
                "id": f"slot-{date_str}-{time_start.replace(':', '')}",
                "date": date_str,
                "time_start": time_start,
                "time_end": time_end,
                "capacity": 10,
                "reserved": 0,
                "active": True
            })

    return slots


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

async def seed_products():
    """Seed products into SQLite"""
    print("\n1. Seeding Products...")

    from src.infrastructure.database.models import ProductModel
    from sqlalchemy import delete

    # Get session from generator
    session_gen = Database.get_session()
    session = await anext(session_gen)

    try:
        # Clear existing
        await session.execute(delete(ProductModel))
        await session.commit()

        # Insert products
        for p in SAMPLE_PRODUCTS:
            product = ProductModel(
                id=p["id"],
                name=p["name"],
                description=p["description"],
                category=p["category"],
                price=p["price"],
                stock=p["stock"],
                sku=p["sku"],
                specifications=p.get("specifications", {}),
                images=[],
            )
            session.add(product)

        await session.commit()
        print(f"   Inserted {len(SAMPLE_PRODUCTS)} products")
    finally:
        await session.close()


async def seed_coupons():
    """Seed coupons into SQLite"""
    print("\n2. Seeding Coupons...")

    from src.infrastructure.database.models import CouponModel
    from sqlalchemy import delete

    session_gen = Database.get_session()
    session = await anext(session_gen)

    try:
        # Clear existing
        await session.execute(delete(CouponModel))
        await session.commit()

        # Insert coupons
        for c in SAMPLE_COUPONS:
            coupon = CouponModel(
                id=c["id"],
                code=c["code"],
                discount_type=c["discount_type"],
                discount_value=c["discount_value"],
                min_purchase=c["min_purchase"],
                max_uses=c["max_uses"],
                current_uses=c["current_uses"],
                valid_until=c["valid_until"],
                active=c["active"]
            )
            session.add(coupon)

        await session.commit()
        print(f"   Inserted {len(SAMPLE_COUPONS)} coupons")
        for c in SAMPLE_COUPONS:
            print(f"      - {c['code']}: {c['discount_value']}{'%' if c['discount_type'] == 'percentage' else '$'} off")
    finally:
        await session.close()


async def seed_districts():
    """Seed districts into SQLite"""
    print("\n3. Seeding Districts...")

    from src.infrastructure.database.models import DistrictModel
    from sqlalchemy import delete

    session_gen = Database.get_session()
    session = await anext(session_gen)

    try:
        # Clear existing
        await session.execute(delete(DistrictModel))
        await session.commit()

        # Insert districts
        for d in SAMPLE_DISTRICTS:
            district = DistrictModel(
                id=d["id"],
                name=d["name"],
                delivery_cost=d["delivery_cost"],
                min_purchase=d["min_purchase"],
                active=True
            )
            session.add(district)

        await session.commit()
        print(f"   Inserted {len(SAMPLE_DISTRICTS)} districts")
    finally:
        await session.close()


async def seed_delivery_slots():
    """Seed delivery slots into SQLite"""
    print("\n4. Seeding Delivery Slots...")

    slots = generate_delivery_slots()

    from src.infrastructure.database.models import DeliverySlotModel
    from sqlalchemy import delete

    session_gen = Database.get_session()
    session = await anext(session_gen)

    try:
        # Clear existing
        await session.execute(delete(DeliverySlotModel))
        await session.commit()

        # Insert slots
        for s in slots:
            slot = DeliverySlotModel(
                id=s["id"],
                date=s["date"],
                time_start=s["time_start"],
                time_end=s["time_end"],
                capacity=s["capacity"],
                reserved=s["reserved"],
                active=s["active"]
            )
            session.add(slot)

        await session.commit()
        print(f"   Inserted {len(slots)} delivery slots (7 days x 4 slots)")
    finally:
        await session.close()


async def seed_vectorstore():
    """Index products in ChromaDB"""
    print("\n5. Indexing Products in ChromaDB...")

    await ChromaStore.initialize(settings.chroma_persist_dir)

    success_count = 0
    for p in SAMPLE_PRODUCTS:
        success = await ChromaStore.upsert_product(
            product_id=p["id"],
            name=p["name"],
            description=p["description"],
            category=p["category"],
            sku=p["sku"]
        )
        if success:
            success_count += 1

    print(f"   Indexed {success_count}/{len(SAMPLE_PRODUCTS)} products")

    stats = await ChromaStore.get_stats()
    print(f"   ChromaDB: {stats.get('products_indexed', 0)} total indexed")


async def test_search():
    """Test semantic search"""
    print("\n6. Testing Semantic Search...")

    queries = [
        ("muebles para sala", "Muebles"),
        ("iluminacion moderna", "Iluminacion"),
        ("escritorio para trabajar", "Oficina"),
        ("decoracion hogar", "Decoracion"),
    ]

    for query, expected in queries:
        results = await ChromaStore.search_products(query, top_k=2)
        if results:
            top_result = results[0]["metadata"].get("name", "N/A")
            print(f"   '{query}' -> {top_result}")
        else:
            print(f"   '{query}' -> No results")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("=" * 60)
    print("SEED LOCAL DATABASE")
    print("=" * 60)

    try:
        # Initialize database
        await Database.connect()

        # Seed all data
        await seed_products()
        await seed_coupons()
        await seed_districts()
        await seed_delivery_slots()
        await seed_vectorstore()
        await test_search()

        # Disconnect
        await Database.disconnect()

        print("\n" + "=" * 60)
        print("SEED COMPLETED!")
        print("=" * 60)
        print(f"""
Summary:
  - {len(SAMPLE_PRODUCTS)} products
  - {len(SAMPLE_COUPONS)} coupons
  - {len(SAMPLE_DISTRICTS)} districts
  - {len(generate_delivery_slots())} delivery slots

Available Coupons:
  - BIENVENIDO10: 10% off (min $100)
  - ENVIOGRATIS: $15 off (min $200)
  - DESCUENTO20: 20% off (min $500)
  - VERANO2024: 15% off (min $150)

Start the API:
  uvicorn src.main:app --reload
""")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
