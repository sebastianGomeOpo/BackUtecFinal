"""
Seed districts of Lima with shipping rates
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings


# Districts of Lima with shipping rates (in USD)
LIMA_DISTRICTS = [
    # Centro de Lima - Zona 1 (más económico)
    {"name": "Cercado de Lima", "zone": 1, "rate": 5.00},
    {"name": "Breña", "zone": 1, "rate": 5.00},
    {"name": "La Victoria", "zone": 1, "rate": 5.00},
    {"name": "Rímac", "zone": 1, "rate": 5.00},
    
    # Zona 2 - Distritos cercanos
    {"name": "San Isidro", "zone": 2, "rate": 8.00},
    {"name": "Miraflores", "zone": 2, "rate": 8.00},
    {"name": "Barranco", "zone": 2, "rate": 8.00},
    {"name": "San Borja", "zone": 2, "rate": 8.00},
    {"name": "Surquillo", "zone": 2, "rate": 8.00},
    {"name": "Lince", "zone": 2, "rate": 8.00},
    {"name": "Jesús María", "zone": 2, "rate": 8.00},
    {"name": "Magdalena del Mar", "zone": 2, "rate": 8.00},
    {"name": "Pueblo Libre", "zone": 2, "rate": 8.00},
    {"name": "San Miguel", "zone": 2, "rate": 8.00},
    
    # Zona 3 - Distritos intermedios
    {"name": "Surco", "zone": 3, "rate": 12.00},
    {"name": "La Molina", "zone": 3, "rate": 12.00},
    {"name": "San Luis", "zone": 3, "rate": 10.00},
    {"name": "Ate", "zone": 3, "rate": 12.00},
    {"name": "Santa Anita", "zone": 3, "rate": 12.00},
    {"name": "El Agustino", "zone": 3, "rate": 10.00},
    {"name": "San Juan de Miraflores", "zone": 3, "rate": 12.00},
    {"name": "Villa María del Triunfo", "zone": 3, "rate": 12.00},
    {"name": "Villa El Salvador", "zone": 3, "rate": 12.00},
    {"name": "Chorrillos", "zone": 3, "rate": 10.00},
    
    # Zona 4 - Distritos del norte
    {"name": "Los Olivos", "zone": 4, "rate": 15.00},
    {"name": "Independencia", "zone": 4, "rate": 15.00},
    {"name": "San Martín de Porres", "zone": 4, "rate": 15.00},
    {"name": "Comas", "zone": 4, "rate": 18.00},
    {"name": "Carabayllo", "zone": 4, "rate": 20.00},
    {"name": "Puente Piedra", "zone": 4, "rate": 20.00},
    {"name": "Santa Rosa", "zone": 4, "rate": 22.00},
    {"name": "Ancón", "zone": 4, "rate": 25.00},
    
    # Zona 5 - Distritos del este
    {"name": "Lurigancho", "zone": 5, "rate": 18.00},
    {"name": "San Juan de Lurigancho", "zone": 5, "rate": 18.00},
    {"name": "Chaclacayo", "zone": 5, "rate": 22.00},
    {"name": "Lurin", "zone": 5, "rate": 20.00},
    {"name": "Pachacamac", "zone": 5, "rate": 22.00},
    {"name": "Cieneguilla", "zone": 5, "rate": 25.00},
    
    # Callao
    {"name": "Callao", "zone": 3, "rate": 12.00},
    {"name": "Bellavista", "zone": 3, "rate": 12.00},
    {"name": "La Perla", "zone": 3, "rate": 12.00},
    {"name": "La Punta", "zone": 3, "rate": 12.00},
    {"name": "Carmen de la Legua", "zone": 3, "rate": 12.00},
    {"name": "Ventanilla", "zone": 4, "rate": 18.00},
]


async def seed_districts():
    """Seed districts collection"""
    print("🌍 Seeding Lima districts with shipping rates...")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    
    # Clear existing districts
    await db.districts.delete_many({})
    print(f"🗑️  Cleared existing districts")
    
    # Insert districts
    result = await db.districts.insert_many(LIMA_DISTRICTS)
    print(f"✅ Inserted {len(result.inserted_ids)} districts")
    
    # Create index on name for faster searches
    await db.districts.create_index("name")
    print("📇 Created index on district name")
    
    # Show sample
    print("\n📋 Sample districts:")
    for district in LIMA_DISTRICTS[:5]:
        print(f"   - {district['name']}: ${district['rate']:.2f} (Zona {district['zone']})")
    
    print(f"\n✨ Total districts: {len(LIMA_DISTRICTS)}")
    print("\n✅ Districts seeded successfully!")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_districts())
