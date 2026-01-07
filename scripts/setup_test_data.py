"""
Script para verificar y crear datos de prueba en MongoDB y Pinecone
También configura Cloudflare R2 para imágenes firmadas
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
import hashlib
import hmac
from urllib.parse import quote

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pinecone import Pinecone

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "AgentN")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "products-catalog")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Cloudflare R2
R2_ENDPOINT = os.getenv("CLOUDFLARE_R2_ENDPOINT")
R2_BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET")
R2_ACCESS_KEY = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")


# Sample products for testing
SAMPLE_PRODUCTS = [
    {
        "id": str(uuid.uuid4()),
        "name": "Sofá Moderno 3 Cuerpos",
        "description": "Sofá de 3 cuerpos con tapizado de tela premium, estructura de madera y patas de metal. Ideal para sala de estar moderna.",
        "category": "Sala",
        "price": 1299.99,
        "stock": 15,
        "sku": "SOF-MOD-001",
        "images": [],
        "specifications": {"color": "Gris", "material": "Tela premium", "dimensiones": "220x90x85 cm"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Mesa de Centro Nórdica",
        "description": "Mesa de centro estilo nórdico con tapa de madera de roble y patas de metal negro. Diseño minimalista y elegante.",
        "category": "Sala",
        "price": 349.99,
        "stock": 25,
        "sku": "MES-CEN-001",
        "images": [],
        "specifications": {"color": "Roble natural", "material": "Madera de roble", "dimensiones": "120x60x45 cm"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Lámpara de Pie Industrial",
        "description": "Lámpara de pie estilo industrial con base de metal negro y pantalla ajustable. Perfecta para iluminación de lectura.",
        "category": "Iluminación",
        "price": 189.99,
        "stock": 30,
        "sku": "LAM-PIE-001",
        "images": [],
        "specifications": {"color": "Negro mate", "material": "Metal", "altura": "165 cm"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Alfombra Geométrica Moderna",
        "description": "Alfombra con diseño geométrico moderno, pelo corto y fácil de limpiar. Ideal para sala o dormitorio.",
        "category": "Decoración",
        "price": 249.99,
        "stock": 20,
        "sku": "ALF-GEO-001",
        "images": [],
        "specifications": {"color": "Gris/Blanco", "material": "Polipropileno", "dimensiones": "200x300 cm"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Juego de Sábanas Premium",
        "description": "Juego de sábanas de algodón egipcio 400 hilos. Incluye sábana bajera, sábana encimera y 2 fundas de almohada.",
        "category": "Textiles",
        "price": 129.99,
        "stock": 50,
        "sku": "SAB-PRE-001",
        "images": [],
        "specifications": {"color": "Blanco", "material": "Algodón egipcio", "tamaño": "Queen"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Set de Ollas Antiadherentes",
        "description": "Set de 5 ollas antiadherentes con tapa de vidrio. Incluye ollas de 16, 18, 20, 22 y 24 cm.",
        "category": "Cocina",
        "price": 199.99,
        "stock": 35,
        "sku": "OLL-SET-001",
        "images": [],
        "specifications": {"color": "Negro", "material": "Aluminio antiadherente", "piezas": "5 ollas + 5 tapas"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Espejo Decorativo Redondo",
        "description": "Espejo decorativo redondo con marco de metal dorado. Perfecto para entrada o sala de estar.",
        "category": "Decoración",
        "price": 159.99,
        "stock": 18,
        "sku": "ESP-RED-001",
        "images": [],
        "specifications": {"color": "Dorado", "material": "Metal y vidrio", "diámetro": "80 cm"},
        "metadata": {}
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Cama King con Cabecera",
        "description": "Cama King size con cabecera tapizada en tela gris. Estructura de madera maciza y diseño contemporáneo.",
        "category": "Dormitorio",
        "price": 1599.99,
        "stock": 8,
        "sku": "CAM-KIN-001",
        "images": [],
        "specifications": {"color": "Gris", "material": "Madera y tela", "tamaño": "King (200x200 cm)"},
        "metadata": {}
    }
]


async def get_embedding(text: str) -> list:
    """Get embedding from OpenAI"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "input": text,
                "model": "text-embedding-ada-002"
            },
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def check_mongodb():
    """Check MongoDB connection and products"""
    print("\n" + "="*60)
    print("VERIFICANDO MONGODB ATLAS")
    print("="*60)
    
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[MONGODB_DB_NAME]
        
        # Ping
        await client.admin.command('ping')
        print(f"✅ Conexión exitosa a MongoDB Atlas")
        print(f"   Database: {MONGODB_DB_NAME}")
        
        # Check collections
        collections = await db.list_collection_names()
        print(f"   Colecciones: {collections}")
        
        # Check products
        products_count = await db.products.count_documents({})
        print(f"   Productos en DB: {products_count}")
        
        if products_count > 0:
            # Show sample products
            cursor = db.products.find({}).limit(3)
            print("\n   Muestra de productos:")
            async for product in cursor:
                print(f"   - {product.get('name')} (${product.get('price')}) - Stock: {product.get('stock')}")
        
        # Check users collection
        users_count = await db.users.count_documents({})
        print(f"\n   Usuarios en DB: {users_count}")
        
        # Check escalations collection
        escalations_count = await db.escalations.count_documents({})
        print(f"   Escalaciones en DB: {escalations_count}")
        
        client.close()
        return products_count
        
    except Exception as e:
        print(f"❌ Error conectando a MongoDB: {e}")
        return 0


def check_pinecone():
    """Check Pinecone index"""
    print("\n" + "="*60)
    print("VERIFICANDO PINECONE")
    print("="*60)
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # List indexes
        indexes = pc.list_indexes()
        index_names = [idx['name'] for idx in indexes]
        print(f"✅ Conexión exitosa a Pinecone")
        print(f"   Indexes disponibles: {index_names}")
        
        if PINECONE_INDEX_NAME in index_names:
            index = pc.Index(PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            print(f"\n   Index '{PINECONE_INDEX_NAME}':")
            print(f"   - Vectores totales: {stats.total_vector_count}")
            print(f"   - Dimensión: {stats.dimension}")
            return stats.total_vector_count
        else:
            print(f"⚠️  Index '{PINECONE_INDEX_NAME}' no existe")
            return 0
            
    except Exception as e:
        print(f"❌ Error conectando a Pinecone: {e}")
        return 0


async def create_sample_products():
    """Create sample products in MongoDB and Pinecone"""
    print("\n" + "="*60)
    print("CREANDO PRODUCTOS DE PRUEBA")
    print("="*60)
    
    try:
        # MongoDB
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[MONGODB_DB_NAME]
        
        # Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        
        created_count = 0
        
        for product in SAMPLE_PRODUCTS:
            # Check if product with same SKU exists
            existing = await db.products.find_one({"sku": product["sku"]})
            if existing:
                print(f"⏭️  Producto ya existe: {product['name']}")
                continue
            
            # Insert to MongoDB
            await db.products.insert_one(product)
            print(f"✅ MongoDB: {product['name']}")
            
            # Create embedding and insert to Pinecone
            product_text = f"{product['name']} {product['description']} Categoría: {product['category']}"
            embedding = await get_embedding(product_text)
            
            # Upsert to Pinecone
            index.upsert(vectors=[{
                "id": product["id"],
                "values": embedding,
                "metadata": {
                    "name": product["name"],
                    "description": product["description"],
                    "category": product["category"],
                    "sku": product["sku"],
                    "images": product["images"]
                }
            }])
            print(f"✅ Pinecone: {product['name']}")
            
            created_count += 1
        
        client.close()
        print(f"\n📦 Total productos creados: {created_count}")
        return created_count
        
    except Exception as e:
        print(f"❌ Error creando productos: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def create_test_user():
    """Create a test user in MongoDB"""
    print("\n" + "="*60)
    print("CREANDO USUARIO DE PRUEBA")
    print("="*60)
    
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[MONGODB_DB_NAME]
        
        test_user = {
            "user_id": "test-user-001",
            "name": "Juan Pérez",
            "purchase_history": [
                {"product_name": "Sofá Clásico", "date": "2024-01-15"},
                {"product_name": "Lámpara de Mesa", "date": "2024-02-20"}
            ],
            "preferences": {
                "tone": "friendly",
                "size": "L",
                "favorite_color": "azul"
            },
            "created_at": datetime.utcnow().isoformat()
        }
        
        existing = await db.users.find_one({"user_id": test_user["user_id"]})
        if existing:
            print(f"⏭️  Usuario ya existe: {test_user['name']}")
        else:
            await db.users.insert_one(test_user)
            print(f"✅ Usuario creado: {test_user['name']} (ID: {test_user['user_id']})")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error creando usuario: {e}")


async def main():
    """Main function"""
    print("\n" + "="*60)
    print("SETUP DE DATOS DE PRUEBA - SALES AGENT")
    print("="*60)
    
    # 1. Check MongoDB
    mongo_count = await check_mongodb()
    
    # 2. Check Pinecone
    pinecone_count = check_pinecone()
    
    # 3. Create products if needed
    if mongo_count == 0 or pinecone_count == 0:
        print("\n⚠️  No hay productos, creando datos de prueba...")
        await create_sample_products()
    else:
        print("\n✅ Ya existen productos en la base de datos")
    
    # 4. Create test user
    await create_test_user()
    
    # 5. Final verification
    print("\n" + "="*60)
    print("VERIFICACIÓN FINAL")
    print("="*60)
    
    final_mongo = await check_mongodb()
    final_pinecone = check_pinecone()
    
    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    print(f"MongoDB productos: {final_mongo}")
    print(f"Pinecone vectores: {final_pinecone}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
