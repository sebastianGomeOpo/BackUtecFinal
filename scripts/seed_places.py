"""
Seed script for Places POC2 - Santiago places
Adds sample places to MongoDB and Pinecone
"""
import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.mongodb import MongoDB
from src.infrastructure.vectorstore.places_pinecone_store import PlacesPineconeStore
from src.domain.entities import PlacePost, Location


SAMPLE_PLACES = [
    {
        "id": "place_001",
        "image_url": "https://images.unsplash.com/photo-1554118811-1e0d58224f24",
        "title": "Cafetería Vista Hermosa",
        "description": "El mejor café artesanal de Providencia. Ambiente acogedor con terraza al aire libre, perfecto para trabajar o una conversación tranquila. Especialidad en café de grano único y repostería casera.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6119, -33.4249],  # Providencia
            "address": "Av. Providencia 1234, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["café", "brunch", "terraza", "wifi", "pet-friendly"]
    },
    {
        "id": "place_002",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Restaurante Sabores de Chile",
        "description": "Cocina chilena auténtica en pleno corazón de Santiago Centro. Destacan las empanadas de pino caseras y el pastel de choclo. Ambiente familiar y precios accesibles.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6693, -33.4372],  # Santiago Centro
            "address": "Calle Bandera 567, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["comida chilena", "almuerzo", "familiar", "tradicional"]
    },
    {
        "id": "place_003",
        "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64",
        "title": "Parque Bicentenario",
        "description": "Hermoso parque con lagunas artificiales, áreas verdes y juegos infantiles. Ideal para picnic familiar, trotar o simplemente relajarse. Cuenta con estacionamiento y está rodeado de cafeterías.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.5789, -33.4050],  # Vitacura
            "address": "Av. Bicentenario 3800, Vitacura",
            "neighborhood": "Vitacura"
        },
        "tags": ["parque", "familia", "outdoor", "deporte", "naturaleza"]
    },
    {
        "id": "place_004",
        "image_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477",
        "title": "Centro Cultural Gabriela Mistral (GAM)",
        "description": "Principal centro cultural de Santiago. Ofrece teatro, danza, música y exposiciones de arte contemporáneo. Arquitectura icónica y programación variada para todos los públicos.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6506, -33.4372],  # Santiago Centro
            "address": "Av. Libertador Bernardo O'Higgins 227, Santiago",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["cultura", "teatro", "arte", "exposiciones", "música"]
    },
    {
        "id": "place_005",
        "image_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b",
        "title": "Barrio Italia",
        "description": "Barrio bohemio con tiendas vintage, galerías de arte, cafés y restaurantes. Perfecto para pasear, buscar antigüedades y disfrutar de la gastronomía. Los domingos hay feria de diseño local.",
        "category": "Compras",
        "location": {
            "coordinates": [-70.6350, -33.4525],  # Ñuñoa
            "address": "Av. Italia altura 1400, Ñuñoa",
            "neighborhood": "Ñuñoa"
        },
        "tags": ["compras", "vintage", "arte", "paseo", "diseño"]
    },
    {
        "id": "place_006",
        "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5",
        "title": "Sky Costanera",
        "description": "El mirador más alto de Sudamérica en el piso 61 y 62 del Costanera Center. Vista 360° de Santiago y la cordillera. Incluye cafetería y tienda de souvenirs. Imperdible al atardecer.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.6065, -33.4172],  # Providencia
            "address": "Av. Andrés Bello 2425, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["mirador", "turismo", "vista", "panorámica", "fotografía"]
    },
    {
        "id": "place_007",
        "image_url": "https://images.unsplash.com/photo-1559339352-11d035aa65de",
        "title": "Mercado Central",
        "description": "Mercado histórico famoso por sus mariscos frescos y cocinerías tradicionales. Arquitectura patrimonial del siglo XIX. Ideal para almorzar platos típicos chilenos como caldillo de congrio o paila marina.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6527, -33.4353],  # Santiago Centro
            "address": "San Pablo 967, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["mariscos", "tradicional", "almuerzo", "patrimonio", "turismo"]
    },
    {
        "id": "place_008",
        "image_url": "https://images.unsplash.com/photo-1571902943202-507ec2618e8f",
        "title": "Cerro San Cristóbal",
        "description": "Parque metropolitano con senderos para trekking, funicular y teleférico. En la cima está el Santuario de la Inmaculada Concepción con vista panorámica de Santiago. Incluye zoológico y piscinas en verano.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.6344, -33.4269],  # Recoleta
            "address": "Pío Nono 445, Recoleta",
            "neighborhood": "Recoleta"
        },
        "tags": ["trekking", "deporte", "naturaleza", "vista", "familia"]
    },
    {
        "id": "place_009",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Patio Bellavista",
        "description": "Centro gastronómico y cultural al aire libre. Más de 30 restaurantes, bares y tiendas. Ambiente bohemio cerca del Cerro San Cristóbal. Perfecto para cenar y salir de noche.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6322, -33.4331],  # Providencia/Recoleta
            "address": "Pío Nono 73, Providencia",
            "neighborhood": "Bellavista"
        },
        "tags": ["restaurantes", "vida nocturna", "bohemio", "variedad", "ambiente"]
    },
    {
        "id": "place_010",
        "image_url": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1",
        "title": "Museo de la Memoria",
        "description": "Museo dedicado a las víctimas de violaciones a derechos humanos durante la dictadura militar (1973-1990). Exposiciones permanentes y temporales. Arquitectura moderna. Entrada gratuita.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6833, -33.4406],  # Quinta Normal
            "address": "Matucana 501, Quinta Normal",
            "neighborhood": "Quinta Normal"
        },
        "tags": ["museo", "historia", "cultura", "educación", "gratuito"]
    },
    {
        "id": "place_011",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Café de la Plaza",
        "description": "Café tranquilo con terraza al aire libre en plena Plaza de Armas. Ideal para almorzar mientras ves el movimiento del centro histórico. Tienen ensaladas frescas, sándwiches gourmet y pasta. El ambiente es relajado y tienen buena sombra en verano.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6506, -33.4378],  # Santiago Centro - Plaza de Armas
            "address": "Portal Fernández Concha 981, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["café", "terraza", "al aire libre", "almuerzo", "plaza", "centro histórico"]
    },
    {
        "id": "place_012",
        "image_url": "https://images.unsplash.com/photo-1554118811-1e0d58224f24",
        "title": "Jardín Secreto",
        "description": "Restaurante escondido con patio interior lleno de plantas. Queda cerca del Palacio de la Moneda. Perfecto para almorzar al aire libre en un ambiente tranquilo lejos del ruido de la calle. Tienen menú del día y opciones vegetarianas.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6550, -33.4420],  # Santiago Centro - cerca de La Moneda
            "address": "Morandé 351, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["restaurante", "patio", "al aire libre", "almuerzo", "tranquilo", "vegetariano"]
    },
    {
        "id": "place_013",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Terraza Lastarria",
        "description": "Café y bistró con terraza amplia en el Barrio Lastarria. Excelente para almorzar al aire libre con vista a la calle peatonal. Tienen tablas de quesos, ensaladas y platos del día. Muy buen ambiente cultural.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6450, -33.4385],  # Santiago Centro - Lastarria
            "address": "José Victorino Lastarria 307, Santiago Centro",
            "neighborhood": "Lastarria"
        },
        "tags": ["café", "terraza", "al aire libre", "almuerzo", "cultural", "peatonal"]
    },
    {
        "id": "place_014",
        "image_url": "https://images.unsplash.com/photo-1554118811-1e0d58224f24",
        "title": "Patio Brasil",
        "description": "Restaurante con patio al aire libre en el Barrio Brasil. Ambiente bohemio y relajado. Buena comida casera y precios razonables. El patio tiene mesas bajo árboles, perfecto para almorzar tranquilo.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6750, -33.4450],  # Santiago Centro - Barrio Brasil
            "address": "Av. Brasil 53, Santiago Centro",
            "neighborhood": "Barrio Brasil"
        },
        "tags": ["restaurante", "patio", "al aire libre", "almuerzo", "bohemio", "casero"]
    }
]


async def seed_places():
    """Add sample places to MongoDB and Pinecone"""
    print("🌱 Starting Places seed...")
    
    try:
        # Connect to MongoDB
        await MongoDB.connect()
        print("✅ Connected to MongoDB")
        
        # Initialize Pinecone
        await PlacesPineconeStore.initialize()
        print("✅ Connected to Pinecone")
        
        # Get collections
        posts_collection = MongoDB.get_database()["place_posts"]
        vectorstore = PlacesPineconeStore()
        
        # Clear existing data (optional)
        print("🗑️  Clearing existing places...")
        await posts_collection.delete_many({})
        
        # Insert places
        print(f"📝 Inserting {len(SAMPLE_PLACES)} places...")
        
        for place_data in SAMPLE_PLACES:
            # Create PlacePost entity
            post = PlacePost(
                id=place_data["id"],
                image_url=place_data["image_url"],
                title=place_data["title"],
                description=place_data["description"],
                category=place_data["category"],
                location=Location(**place_data["location"]),
                sponsor="Coca-Cola Andina",
                tags=place_data["tags"],
                created_at=datetime.utcnow()
            )
            
            # Save to MongoDB
            await posts_collection.insert_one(post.dict())
            
            # Index in Pinecone
            await vectorstore.upsert_place(post)
            
            print(f"  ✅ {post.title}")
        
        # Create geospatial index
        print("📍 Creating geospatial index...")
        await posts_collection.create_index([("location.coordinates", "2dsphere")])
        
        print(f"\n✅ Seed completed! {len(SAMPLE_PLACES)} places added")
        print("\nPlaces by category:")
        
        # Count by category
        categories = {}
        for place in SAMPLE_PLACES:
            cat = place["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in categories.items():
            print(f"  - {cat}: {count}")
        
        print("\n🎉 Ready to test POC2!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    
    finally:
        await MongoDB.disconnect()
        print("👋 Disconnected from MongoDB")


if __name__ == "__main__":
    asyncio.run(seed_places())
