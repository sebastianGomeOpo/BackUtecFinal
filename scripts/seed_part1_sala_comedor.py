"""
Seed Part 1: Sala y Comedor (15 productos)
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.mongodb import MongoDB
from src.infrastructure.vectorstore.pinecone_store import PineconeStore
from src.infrastructure.repositories.product_repository import MongoProductRepository
from src.domain.entities import Product
import uuid


PRODUCTS = [
    {
        "name": "Sofá Moderno 3 Puestos Premium",
        "description": "Sofá moderno de 3 puestos con tapizado en tela premium importada de alta resistencia. Estructura de madera maciza de pino reforzada y cojines de espuma de alta densidad (35kg/m³) con respaldo reclinable. Color gris perla con patas de madera natural. Dimensiones: 220cm de largo x 95cm de profundidad x 90cm de altura. Ideal para salas de estar contemporáneas y espacios amplios. Incluye 5 cojines decorativos. Resistente a manchas y fácil limpieza.",
        "category": "Muebles de Sala",
        "price": 1299.99,
        "stock": 75,
        "sku": "SOFA-MOD-3P-GRY-PREM"
    },
    {
        "name": "Sofá Seccional en L 5 Puestos",
        "description": "Sofá seccional en forma de L de 5 puestos, perfecto para espacios grandes. Tapizado en cuero sintético italiano de primera calidad, color marrón chocolate. Estructura interna de madera y metal reforzado. Asientos extraíbles para fácil limpieza. Dimensiones: 280cm x 220cm x 85cm de altura. Incluye chaise lounge reversible y almacenamiento oculto bajo los asientos. Capacidad para 6-7 personas cómodamente. Patas cromadas.",
        "category": "Muebles de Sala",
        "price": 1899.99,
        "stock": 55,
        "sku": "SOFA-SECC-L-5P-BRW"
    },
    {
        "name": "Mesa de Centro Minimalista con Vidrio Templado",
        "description": "Mesa de centro rectangular con diseño minimalista moderno. Tapa de vidrio templado de 12mm de espesor, transparente y resistente a rayones. Base de metal negro mate con diseño geométrico. Dimensiones: 120cm x 60cm x 45cm de altura. Incluye repisa inferior de madera MDF color nogal para revistas y decoración. Soporta hasta 50kg. Perfecta para salas contemporáneas. Fácil ensamblaje con instrucciones incluidas.",
        "category": "Muebles de Sala",
        "price": 299.99,
        "stock": 80,
        "sku": "MESA-CENTRO-VID-MIN-120"
    },
    {
        "name": "Mesa de Comedor Extensible Roble Macizo 6-10 Personas",
        "description": "Mesa de comedor extensible de madera maciza de roble europeo con acabado natural barnizado mate. Sistema de extensión con 2 tableros adicionales incluidos que se guardan en la mesa. Dimensiones: 180cm (cerrada) - 260cm (extendida) x 100cm x 76cm de altura. Capacidad de 6 a 10 personas. Patas torneadas estilo clásico-moderno. Peso: 68kg. Perfecta para comedor familiar. Resistente a manchas y humedad. Incluye kit de limpieza especial.",
        "category": "Comedor",
        "price": 1499.99,
        "stock": 60,
        "sku": "MESA-COM-EXT-ROB-6-10"
    },
    {
        "name": "Juego de 6 Sillas de Comedor Tapizadas",
        "description": "Set de 6 sillas de comedor con respaldo alto tapizado en tela antiderrames color gris claro. Estructura de madera de haya maciza con acabado nogal. Asiento acolchado de 8cm de espesor con espuma de alta densidad. Dimensiones por silla: 45cm x 55cm x 102cm de altura. Respaldo ergonómico con botones decorativos. Patas reforzadas con travesaños. Capacidad de carga: 150kg por silla. Incluye protectores de piso de fieltro.",
        "category": "Comedor",
        "price": 749.99,
        "stock": 70,
        "sku": "SILLA-COM-TAP-GRY-SET6"
    },
    {
        "name": "Aparador Buffet Moderno 4 Puertas",
        "description": "Aparador buffet moderno con 4 puertas corredizas y 2 cajones superiores. Fabricado en MDF enchapado en melamina color roble natural con detalles en negro mate. Dimensiones: 180cm x 45cm x 85cm de altura. Interior con 3 repisas ajustables. Sistema de cierre suave en puertas y cajones. Ideal para guardar vajilla, manteles y decoración. Tapa resistente al calor y manchas. Incluye herrajes de montaje para fijación a pared. Capacidad: 80kg distribuidos.",
        "category": "Comedor",
        "price": 699.99,
        "stock": 65,
        "sku": "APAR-BUFF-MOD-4P-ROB"
    },
    {
        "name": "Sillón Reclinable Individual con Reposapiés",
        "description": "Sillón reclinable individual con mecanismo manual y reposapiés extensible. Tapizado en tela tipo terciopelo suave color azul navy. Estructura de madera y metal. Reclinación en 3 posiciones hasta 150 grados. Dimensiones: 85cm x 95cm x 105cm. Reposapiés se extiende hasta 45cm. Reposabrazos anchos y acolchados. Perfecto para sala de TV o rincón de lectura. Incluye bolsillo lateral para control remoto. Capacidad: 130kg.",
        "category": "Muebles de Sala",
        "price": 549.99,
        "stock": 90,
        "sku": "SILLON-RECLIN-IND-NAVY"
    },
    {
        "name": "Estante Biblioteca Modular 5 Niveles",
        "description": "Estante biblioteca modular de 5 niveles con diseño escalonado. Fabricado en madera MDF de 18mm color blanco mate y roble. Dimensiones: 180cm x 35cm x 180cm de altura. Capacidad por repisa: 15kg. Diseño asimétrico moderno ideal para libros, decoración y plantas. Incluye sistema antivuelco para fijación a pared. Repisas de diferentes profundidades (25-35cm). Fácil ensamblaje con instrucciones paso a paso.",
        "category": "Muebles de Sala",
        "price": 399.99,
        "stock": 85,
        "sku": "ESTANTE-BIBL-MOD-5NIV-WH"
    },
    {
        "name": "Mueble TV Entertainment Center 65 pulgadas",
        "description": "Mueble para TV tipo entertainment center para pantallas hasta 65 pulgadas. Fabricado en madera MDF con enchapado nogal oscuro. Dimensiones: 160cm x 42cm x 55cm de altura. Incluye 2 gabinetes laterales con puertas, 2 cajones centrales y compartimento abierto para equipos. Sistema de gestión de cables integrado. Repisas ajustables en gabinetes. Soporta hasta 60kg en la superficie superior. Iluminación LED opcional (no incluida). Patas cromadas ajustables.",
        "category": "Muebles de Sala",
        "price": 799.99,
        "stock": 72,
        "sku": "MUEBLE-TV-ENT-65-NOG"
    },
    {
        "name": "Juego de Mesa de Centro y 2 Mesas Laterales",
        "description": "Set de 3 mesas: 1 mesa de centro y 2 mesas laterales nido. Diseño industrial moderno con tapa de madera maciza recuperada y base de metal negro. Mesa central: 110cm x 60cm x 45cm. Mesas laterales: 50cm x 50cm x 55cm cada una. Acabado natural con barniz protector. Cada pieza con diseño único por vetas naturales. Las mesas laterales se pueden guardar bajo la central. Perfectas para espacios versátiles. Fácil ensamblaje.",
        "category": "Muebles de Sala",
        "price": 649.99,
        "stock": 68,
        "sku": "SET-MESAS-IND-3PZ-REC"
    },
    {
        "name": "Bar Cabinet Moderno con Porta Copas",
        "description": "Mueble bar cabinet con diseño moderno y funcional. Fabricado en madera de pino macizo con acabado cerezo. Dimensiones: 100cm x 45cm x 135cm de altura. Parte superior con bandeja removible, porta botellas para 12 unidades, porta copas para 16 copas, 2 cajones para accesorios y gabinete inferior con puerta. Incluye espejo interior y luz LED. Ideal para comedor o sala. Capacidad: 40kg. Herrajes de bronce envejecido.",
        "category": "Comedor",
        "price": 899.99,
        "stock": 58,
        "sku": "BAR-CAB-MOD-CHER-LED"
    },
    {
        "name": "Mesa de Comedor Redonda Mármol 4-6 Personas",
        "description": "Mesa de comedor redonda con tapa de mármol blanco natural veteado en gris. Base de metal dorado en forma de tulipán estilo mid-century. Diámetro: 120cm, altura: 76cm. Tapa de mármol auténtico de 3cm de espesor pulido y sellado. Perfecta para 4-6 personas. Base muy estable con contrapeso. Ideal para comedores modernos o espacios pequeños. Peso: 85kg. Incluye protectores de piso. Fácil limpieza con paño húmedo.",
        "category": "Comedor",
        "price": 1599.99,
        "stock": 52,
        "sku": "MESA-COM-RED-MARM-120"
    },
    {
        "name": "Sofá Cama Convertible 3 en 1",
        "description": "Sofá cama multifuncional 3 en 1: sofá, cama y chaise lounge. Mecanismo de conversión fácil tipo click-clack. Tapizado en tela antimanchas color gris carbón. Dimensiones como sofá: 200cm x 90cm x 85cm. Como cama: 200cm x 120cm. Incluye 2 cojines decorativos y compartimento de almacenamiento bajo el asiento. Colchón de espuma de 12cm incluido. Estructura de metal reforzada. Ideal para visitas o espacios pequeños. Capacidad de carga: 200kg.",
        "category": "Muebles de Sala",
        "price": 899.99,
        "stock": 78,
        "sku": "SOFA-CAMA-CONV-3EN1-GRY"
    },
    {
        "name": "Banca de Comedor Tapizada 150cm",
        "description": "Banca para comedor tapizada en terciopelo color mostaza. Estructura de madera maciza de roble con patas tipo X color negro mate. Dimensiones: 150cm x 40cm x 48cm de altura. Asiento acolchado de 10cm con espuma de alta densidad y sistema anti-hundimiento. Capacidad para 3 personas adultas. Peso máximo: 300kg. Perfecta para combinar con mesa de comedor. Acabado premium con costuras dobles reforzadas. Incluye protectores de piso.",
        "category": "Comedor",
        "price": 449.99,
        "stock": 82,
        "sku": "BANCA-COM-TAP-MOST-150"
    },
    {
        "name": "Consola Entrada Moderna con Espejo",
        "description": "Set de consola para entrada con espejo rectangular incluido. Consola fabricada en madera MDF con acabado blanco brillante y tapa de mármol sintético. Dimensiones consola: 120cm x 35cm x 80cm. Incluye 2 cajones con sistema de cierre suave. Espejo: 80cm x 100cm con marco dorado. Diseño elegante ideal para entrada o pasillo. Base de la consola con detalles dorados. Capacidad de carga: 25kg. Incluye kit de montaje de espejo.",
        "category": "Muebles de Sala",
        "price": 599.99,
        "stock": 70,
        "sku": "CONSOLA-ENT-ESP-WH-120"
    }
]


async def seed_part1():
    """Seed Sala y Comedor products"""
    await MongoDB.connect()
    await PineconeStore.initialize()
    
    product_repo = MongoProductRepository()
    vectorstore = PineconeStore()
    
    print("🌱 Seeding Part 1: Sala y Comedor (15 productos)...")
    
    for idx, prod_data in enumerate(PRODUCTS, 1):
        try:
            product = Product(
                id=str(uuid.uuid4()),
                name=prod_data["name"],
                description=prod_data["description"],
                category=prod_data["category"],
                price=prod_data["price"],
                stock=prod_data["stock"],
                sku=prod_data["sku"]
            )
            
            await product_repo.create(product)
            await vectorstore.upsert_product(product)
            
            print(f"✅ [{idx}/15] {product.name}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print(f"\n✅ Part 1 complete: 15 productos de Sala y Comedor!")
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_part1())
