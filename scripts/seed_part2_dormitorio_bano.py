"""
Seed Part 2: Dormitorio y Baño (15 productos)
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
        "name": "Cama Queen Size Tapizada con Almacenamiento",
        "description": "Cama queen size con cabecera tapizada en terciopelo gris perla y base con cajones de almacenamiento. Estructura de madera maciza de pino. Dimensiones: 160cm x 200cm (colchón), altura total: 120cm, cabecera acolchada de 10cm de grosor. Base incluye 4 cajones amplios con rieles metálicos y sistema de cierre suave. Capacidad de almacenamiento: 80 litros por cajón. Incluye somier de tablillas de madera reforzadas. Soporta hasta 250kg. Ensamblaje incluye instrucciones detalladas.",
        "category": "Dormitorio",
        "price": 1199.99,
        "stock": 68,
        "sku": "CAMA-QN-TAP-ALM-GRY"
    },
    {
        "name": "Cama King Size Dosel Estilo Romántico",
        "description": "Cama king size con dosel de cuatro postes estilo romántico-moderno. Estructura de metal negro mate con detalles dorados. Dimensiones: 180cm x 200cm (colchón), altura de postes: 220cm. Incluye telas decorativas blancas tipo gasa para cortinas (removibles y lavables). Cabecera de metal con diseño de volutas. Compatible con cualquier colchón king size. Base de somier de metal reforzado. Perfecta para dormitorios amplios y elegantes. Capacidad: 300kg.",
        "category": "Dormitorio",
        "price": 1499.99,
        "stock": 55,
        "sku": "CAMA-KG-DOSEL-ROM-BLK"
    },
    {
        "name": "Juego de Sábanas King Size Bambú Premium",
        "description": "Juego completo de sábanas king size en fibra de bambú 100% orgánica de 800 hilos. Incluye: sábana bajera elástica (180x200cm), sábana encimera (240x280cm) y 2 fundas de almohada (50x70cm). Color blanco nieve con borde satinado. Ultra suave, hipoalergénico, antibacterial natural, termorregulador y eco-friendly. Resistente al encogimiento y decoloración. Certificado OEKO-TEX. Lavable en máquina a 60°C. Más fresco que el algodón en verano y más cálido en invierno.",
        "category": "Ropa de Cama",
        "price": 149.99,
        "stock": 95,
        "sku": "SAB-KING-BAMBU-800-WH"
    },
    {
        "name": "Edredón Nórdico 4 Estaciones King Size",
        "description": "Edredón nórdico premium 4 estaciones con sistema de botones para ajustar grosor. Relleno de plumón de ganso blanco 90% (600 fill power) y 10% plumas finas. Funda exterior 100% algodón egipcio 400 hilos color marfil con diseño acolchado tipo diamante. Tamaño: 240cm x 260cm para cama king. Peso de relleno: 2.5kg (todo el año). Certificado RDS (Responsible Down Standard). Incluye 8 lazos de esquina para funda. Lavable en seco o máquina delicado. Estuche de almacenamiento incluido.",
        "category": "Ropa de Cama",
        "price": 399.99,
        "stock": 72,
        "sku": "EDRED-NORD-4EST-KG-IVO"
    },
    {
        "name": "Closet Modular 6 Puertas con Espejo",
        "description": "Closet armario modular de 6 puertas con espejo central. Fabricado en MDF con enchapado melamínico color roble claro. Dimensiones: 270cm x 60cm x 220cm de altura. Interior organizado con: barra superior para colgar (capacidad 30 ganchos), 6 cajones, 4 repisas ajustables y 2 compartimentos para zapatos (capacidad 16 pares). Puertas con sistema de cierre suave. Espejo central biselado de 180cm. Incluye luz LED interior con sensor. Capacidad total: 150kg distribuidos. Requiere fijación a pared.",
        "category": "Dormitorio",
        "price": 1899.99,
        "stock": 50,
        "sku": "CLOSET-MOD-6P-ESP-ROB"
    },
    {
        "name": "Cómoda Moderna 5 Cajones con Espejo",
        "description": "Cómoda vertical moderna de 5 cajones amplios con espejo horizontal incluido. Fabricada en madera maciza de pino con acabado blanco mate y tiradores dorados. Dimensiones cómoda: 80cm x 45cm x 120cm. Cajones con guías metálicas telescópicas de extensión total y sistema anti-caída. Tapa de mármol sintético resistente. Espejo: 100cm x 60cm con marco a juego. Ideal para dormitorio. Capacidad por cajón: 10kg. Incluye kit anti-vuelco y protectores de piso.",
        "category": "Dormitorio",
        "price": 699.99,
        "stock": 78,
        "sku": "COMODA-MOD-5CAJ-ESP-WH"
    },
    {
        "name": "Juego de Almohadas Viscoelásticas Memory Foam",
        "description": "Set de 2 almohadas viscoelásticas con núcleo de memory foam premium de alta densidad (50kg/m³). Tamaño: 50cm x 70cm, altura ajustable 12-15cm. Funda interior de bambú hipoalergénico y antibacterial. Funda exterior removible con cierre, lavable a máquina, color blanco. Diseño ergonómico que se adapta al cuello y cabeza. Ideal para cualquier posición al dormir. Certificado CertiPUR. Reduce puntos de presión y mejora circulación. Incluye bolsa de transporte.",
        "category": "Ropa de Cama",
        "price": 129.99,
        "stock": 100,
        "sku": "ALMOHADA-VISCO-MF-SET2"
    },
    {
        "name": "Mesa de Noche Flotante con Cajón",
        "description": "Mesa de noche de pared flotante con diseño minimalista. Fabricada en MDF color nogal oscuro con frente en laca blanca. Dimensiones: 45cm x 35cm x 15cm de profundidad. Incluye 1 cajón con sistema push-to-open sin tiradores y 1 compartimento abierto inferior. Incluye kit de montaje oculto para pared (soporta 15kg). Ideal para dormitorios modernos y espacios pequeños. Cable management integrado para cargador de teléfono. Vendida por unidad.",
        "category": "Dormitorio",
        "price": 159.99,
        "stock": 88,
        "sku": "MESA-NOCHE-FLOT-NOG-WH"
    },
    {
        "name": "Tocador con Espejo LED y Taburete",
        "description": "Set completo de tocador moderno con espejo LED, taburete acolchado y organizadores. Tocador: 100cm x 45cm x 75cm en color blanco brillante con 3 cajones y compartimento central. Espejo Hollywood: 60cm x 80cm con 12 luces LED regulables (3 tonos: cálido, neutro, frío) y puerto USB. Taburete tapizado en terciopelo rosa pálido, altura 45cm. Incluye organizadores acrílicos para maquillaje. Perfecto para dormitorio o vestidor. Fácil ensamblaje.",
        "category": "Dormitorio",
        "price": 549.99,
        "stock": 65,
        "sku": "TOCADOR-LED-TAB-WH-PINK"
    },
    {
        "name": "Cobija Sherpa Reversible Queen Peluche",
        "description": "Cobija manta reversible queen size ultra suave. Lado 1: sherpa tipo cordero sintético color crema. Lado 2: microfibra peluche color gris claro. Dimensiones: 200cm x 230cm. Peso: 2.8kg - perfecta para invierno. Anti-pilling, no suelta pelusas. Hipoalergénica y no tóxica. Resistente a decoloración. Lavable en máquina agua fría, secadora temperatura baja. Ideal para cama, sofá o picnic. Incluye bolsa de almacenamiento con cierre. Muy cálida y acogedora.",
        "category": "Ropa de Cama",
        "price": 89.99,
        "stock": 92,
        "sku": "COBIJA-SHERPA-QN-CREAM-GRY"
    },
    {
        "name": "Organizador de Baño 5 Niveles Metal",
        "description": "Estante organizador vertical para baño de 5 niveles en metal cromado resistente al agua. Dimensiones: 40cm x 30cm x 165cm de altura. Repisas de alambre de metal con recubrimiento anti-óxido. Capacidad por nivel: 8kg. Incluye 4 ganchos laterales para toallas. Patas ajustables con niveladores de goma. Perfecto para espacios reducidos. Ideal para toallas, productos de baño y decoración. Fácil ensamblaje sin herramientas. Acabado cromado brillante.",
        "category": "Baño",
        "price": 129.99,
        "stock": 85,
        "sku": "ORG-BANO-5NIV-CHROME"
    },
    {
        "name": "Juego de Toallas Premium 6 Piezas Algodón Egipcio",
        "description": "Set de 6 toallas de lujo en algodón egipcio 700GSM (gramos por metro cuadrado). Incluye: 2 toallas de baño (70x140cm), 2 toallas de mano (50x90cm), 2 toallas faciales (30x30cm). Color gris carbón con borde blanco. Ultra absorbentes, suaves al tacto, secado rápido. Dobladillo doble reforzado con costuras de seguridad. Resistentes a la decoloración después de múltiples lavados. Certificado OEKO-TEX Standard 100. Lavables en máquina. Incluye caja de regalo.",
        "category": "Baño",
        "price": 119.99,
        "stock": 90,
        "sku": "TOALLAS-PREM-6PZ-EGYPT-GRY"
    },
    {
        "name": "Espejo de Baño con Marco LED Antivaho",
        "description": "Espejo de baño rectangular con iluminación LED perimetral integrada y sistema antivaho. Dimensiones: 80cm x 60cm x 4cm de grosor. Luz LED blanca neutra 6000K, consumo eficiente 12W. Interruptor touch sensor con memoria de encendido. Sistema antivaho activado con el LED. Instalación horizontal o vertical. Marco de aluminio resistente a humedad. Cristal de 5mm de alta definición. Certificación IP44 para uso en baño. Incluye kit de montaje completo. Garantía 2 años.",
        "category": "Baño",
        "price": 299.99,
        "stock": 75,
        "sku": "ESPEJO-BANO-LED-ANTIV-80"
    },
    {
        "name": "Cesto de Ropa Doble con Tapa Bambú",
        "description": "Cesto organizador de ropa con 2 compartimentos separados, ideal para clasificar ropa clara y oscura. Estructura de bambú natural ecológico con 2 bolsas de tela de algodón removibles (60 litros cada una). Dimensiones: 70cm x 40cm x 60cm de altura. Tapas independientes con bisagras de metal. Asas laterales de cuerda para transporte. Bolsas lavables con cordón de cierre. Perfecto para baño o lavandería. Resistente a humedad. Ensamblaje rápido incluido.",
        "category": "Baño",
        "price": 149.99,
        "stock": 80,
        "sku": "CESTO-ROPA-2COMP-BAMBU"
    },
    {
        "name": "Alfombra de Baño Memory Foam Antideslizante",
        "description": "Alfombra de baño premium con núcleo de memory foam viscoelástico de 2cm de grosor. Dimensiones: 50cm x 80cm. Superficie superior de microfibra ultra absorbente color gris oscuro. Base antideslizante de goma TPR que no se mueve. Absorbe agua rápidamente y se seca veloz. Ultra suave al tacto, recupera forma original después de pisarla. Lavable en máquina agua fría. Hipoalergénica, no tóxica. Perfecta frente a ducha o bañera. Disponible también en 40x60cm.",
        "category": "Baño",
        "price": 49.99,
        "stock": 100,
        "sku": "ALFOMBRA-BANO-MF-ANTID-GRY"
    }
]


async def seed_part2():
    """Seed Dormitorio y Baño products"""
    await MongoDB.connect()
    await PineconeStore.initialize()
    
    product_repo = MongoProductRepository()
    vectorstore = PineconeStore()
    
    print("🌱 Seeding Part 2: Dormitorio y Baño (15 productos)...")
    
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
    
    print(f"\n✅ Part 2 complete: 15 productos de Dormitorio y Baño!")
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_part2())
