"""
Script to seed the database with sample products
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.mongodb import MongoDB
from src.infrastructure.vectorstore.pinecone_store import PineconeStore
from src.infrastructure.repositories.product_repository import MongoProductRepository
from src.domain.entities import Product
import uuid


async def seed_products():
    """Seed database with sample home products"""
    
    # Connect to databases
    await MongoDB.connect()
    await PineconeStore.initialize()
    
    product_repo = MongoProductRepository()
    vectorstore = PineconeStore()
    
    # Sample products
    products = [
        Product(
            id=str(uuid.uuid4()),
            name="Sofá Moderno 3 Puestos",
            description="Sofá moderno de 3 puestos con tapizado en tela premium. Estructura de madera resistente y cojines de alta densidad. Color gris claro. Ideal para salas de estar contemporáneas.",
            category="Muebles de Sala",
            price=899.99,
            stock=15,
            sku="SOFA-MOD-3P-GRY",
            images=["https://example.com/sofa1.jpg"],
            specifications={
                "dimensiones": "210cm x 90cm x 85cm",
                "material": "Tela premium, madera",
                "color": "Gris claro",
                "peso": "45kg"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Mesa de Comedor Extensible",
            description="Mesa de comedor extensible de madera maciza de roble. Capacidad de 6 a 8 personas. Acabado natural barnizado. Sistema de extensión fácil de usar.",
            category="Comedor",
            price=649.99,
            stock=8,
            sku="MESA-COM-EXT-ROB",
            images=["https://example.com/mesa1.jpg"],
            specifications={
                "dimensiones": "160cm-200cm x 90cm x 75cm",
                "material": "Madera de roble",
                "capacidad": "6-8 personas",
                "peso": "35kg"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Juego de Sábanas King Size",
            description="Juego de sábanas de algodón egipcio 600 hilos. Incluye sábana bajera, sábana encimera y 2 fundas de almohada. Suave y transpirable. Color blanco.",
            category="Ropa de Cama",
            price=89.99,
            stock=30,
            sku="SAB-KING-ALG-WHT",
            images=["https://example.com/sabanas1.jpg"],
            specifications={
                "tamaño": "King Size (200x200cm)",
                "material": "Algodón egipcio 600 hilos",
                "color": "Blanco",
                "incluye": "3 piezas"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Lámpara de Pie Moderna",
            description="Lámpara de pie con diseño minimalista. Base metálica negra y pantalla de tela beige. Ideal para lectura. Interruptor de pie y regulador de intensidad.",
            category="Iluminación",
            price=129.99,
            stock=20,
            sku="LAMP-PIE-MOD-BLK",
            images=["https://example.com/lampara1.jpg"],
            specifications={
                "altura": "165cm",
                "material": "Metal, tela",
                "tipo_bombilla": "E27, LED",
                "potencia_maxima": "60W"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Alfombra Moderna Geométrica",
            description="Alfombra moderna con diseño geométrico. Tejido de pelo corto resistente. Colores grises y blancos. Fácil de limpiar. Perfecta para sala o dormitorio.",
            category="Decoración",
            price=159.99,
            stock=12,
            sku="ALF-GEO-GRY-200",
            images=["https://example.com/alfombra1.jpg"],
            specifications={
                "dimensiones": "200cm x 150cm",
                "material": "Polipropileno",
                "grosor": "10mm",
                "diseño": "Geométrico moderno"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Cama Queen Size con Cabecera",
            description="Cama queen size con cabecera tapizada en cuero sintético. Base reforzada con tablillas de madera. Diseño elegante y moderno. Color gris oscuro.",
            category="Dormitorio",
            price=549.99,
            stock=10,
            sku="CAMA-QN-CAB-GRY",
            images=["https://example.com/cama1.jpg"],
            specifications={
                "tamaño": "Queen (160x200cm)",
                "material": "Madera, cuero sintético",
                "altura_cabecera": "110cm",
                "color": "Gris oscuro"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Set de Ollas Antiadherentes 8 Piezas",
            description="Set completo de ollas y sartenes antiadherentes. Recubrimiento de cerámica libre de PFOA. Mangos de silicona resistentes al calor. Apto para todas las cocinas.",
            category="Cocina",
            price=179.99,
            stock=25,
            sku="OLLAS-SET-8P-CER",
            images=["https://example.com/ollas1.jpg"],
            specifications={
                "piezas": "8 piezas",
                "material": "Aluminio con cerámica",
                "incluye": "Ollas 18/20/24cm, sartenes 20/28cm, tapas",
                "apto": "Gas, eléctrico, inducción"
            }
        ),
        Product(
            id=str(uuid.uuid4()),
            name="Espejo Decorativo Circular",
            description="Espejo decorativo circular con marco dorado. Diseño elegante y moderno. Perfecto para entrada, sala o dormitorio. Incluye sistema de montaje.",
            category="Decoración",
            price=79.99,
            stock=18,
            sku="ESP-CIR-ORO-80",
            images=["https://example.com/espejo1.jpg"],
            specifications={
                "diametro": "80cm",
                "material_marco": "Metal dorado",
                "grosor": "5cm",
                "peso": "3.5kg"
            }
        )
    ]
    
    print("🌱 Seeding database with products...")
    
    for product in products:
        try:
            # Save to MongoDB
            await product_repo.create(product)
            
            # Index in Pinecone
            await vectorstore.upsert_product(product)
            
            print(f"✅ Added: {product.name}")
        except Exception as e:
            print(f"❌ Error adding {product.name}: {str(e)}")
    
    print(f"\n✅ Seeded {len(products)} products successfully!")
    
    # Disconnect
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_products())
