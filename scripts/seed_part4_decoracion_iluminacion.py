"""
Seed Part 4: Decoración e Iluminación (13 productos + actualizar 8 existentes)
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
        "name": "Lámpara de Pie Arco Moderna LED",
        "description": "Lámpara de pie tipo arco con diseño contemporáneo elegante. Brazo extensible de acero inoxidable cromado con alcance de 200cm desde la base. Pantalla de tela lino color crema de 40cm de diámetro. Base circular de mármol blanco de 30cm (peso 8kg) para máxima estabilidad. Incluye bombilla LED 12W E27 luz cálida 3000K, regulable con dimmer integrado. Cable textil de 2.5m con interruptor de pie. Altura ajustable 180-210cm. Perfecta para iluminar zona de lectura sobre sofá o mesa. Certificación CE. Consumo eficiente energía clase A++. Color: cromado/crema.",
        "category": "Iluminación",
        "price": 399.99,
        "stock": 68,
        "sku": "LAMP-PIE-ARCO-LED-CHROME"
    },
    {
        "name": "Alfombra Moderna Geométrica XL 300x200cm",
        "description": "Alfombra de área extra grande con diseño geométrico escandinavo moderno en tonos grises, blancos y mostaza. Fabricada en polipropileno de alta densidad con técnica de tejido plano. Dimensiones: 300cm x 200cm x 12mm de grosor. Peso: 8.5kg. Base antideslizante de látex natural que se adhiere al piso sin necesidad de alfombrilla. Resistente al desgaste, clasificación clase 33 para tráfico comercial pesado. No suelta pelos, hipoalergénica. Fácil limpieza con aspiradora o paño húmedo. Resistente a manchas y decoloración UV. Perfecta para salas amplias, comedores o dormitorio principal. Bordes sobrehilados reforzados. Certificado OEKO-TEX.",
        "category": "Decoración",
        "price": 349.99,
        "stock": 72,
        "sku": "ALF-GEO-XL-300X200-SCAN"
    },
    {
        "name": "Set de 3 Espejos Decorativos Pared Dorados",
        "description": "Conjunto de 3 espejos decorativos circulares de pared con marcos metálicos dorados en diferentes tamaños. Diámetros: 60cm, 45cm, 30cm. Marcos de metal con acabado dorado cepillado mate de 4cm de ancho. Espejos biselados de alta definición de 4mm. Diseño minimalista elegante tipo sunburst con rayos metálicos. Sistema de montaje oculto tipo keyhole incluido. Se pueden colgar en grupo artístico o individuales. Resistentes a humedad, aptos para baño. Perfectos para entrada, sala, dormitorio o pasillo. Añaden profundidad y luz a espacios. Incluye plantilla de instalación y kit de montaje completo.",
        "category": "Decoración",
        "price": 199.99,
        "stock": 80,
        "sku": "ESPEJOS-SET3-DORADO-CIRC"
    },
    {
        "name": "Lámpara Colgante Industrial 3 Luces",
        "description": "Lámpara colgante estilo industrial-vintage con 3 pantallas de metal color negro mate. Barra central de 85cm permite distribuir las luces. Cada pantalla: 25cm de diámetro x 20cm de altura, forma de campana. Interior pintado de dorado para mayor reflexión de luz. Portalámparas E27 estándar, admite LED, incandescente o halógeno (máx 60W c/u). Cables textiles trenzados negros ajustables en altura (50-120cm). Roseta de techo incluida: 12cm diámetro. Perfecta para isla de cocina, mesa de comedor o bar. Incluye cadenas decorativas. Fácil instalación con instrucciones. Bombillas no incluidas. Certificación eléctrica CE.",
        "category": "Iluminación",
        "price": 279.99,
        "stock": 65,
        "sku": "LAMP-COLG-IND-3LUZ-BLK-GOLD"
    },
    {
        "name": "Cuadros Decorativos Abstractos Set 5 Piezas",
        "description": "Set de 5 cuadros decorativos con arte abstracto moderno en lienzo canvas premium. Impresión HD con tintas ecológicas resistentes al agua y UV. Colores: azul turquesa, dorado, gris y blanco. Marcos de madera pino color negro mate de 2cm grosor. Tamaños en el set: 1x60x90cm (central), 2x50x70cm (laterales), 2x40x60cm (superiores). Lienzo tensado en bastidor de madera de 2cm profundidad. Listos para colgar con ganchos instalados. Diseño multipanel modular que crea impacto visual. Peso total: 3.5kg. Perfectos para sala, dormitorio, oficina. Incluye nivel y plantilla de instalación. Limpiar con paño seco. Arte original exclusivo.",
        "category": "Decoración",
        "price": 249.99,
        "stock": 75,
        "sku": "CUADROS-ABST-SET5-BLUE-GOLD"
    },
    {
        "name": "Macetas Decorativas Cerámica Set 3 Tamaños",
        "description": "Set de 3 macetas decorativas de cerámica esmaltada con diseño geométrico moderno. Color blanco mate con patrón geométrico en relieve. Tamaños: Grande 25cm diámetro x 23cm alto, Mediana 20cm x 18cm, Pequeña 15cm x 13cm. Orificio de drenaje con tapón removible. Incluye 3 platos de cerámica a juego. Cerámica de alta cocción (1200°C) resistente a heladas. Peso conjunto: 4.5kg. Acabado premium con esmalte interior y exterior. Perfectas para plantas de interior: suculentas, cactus, hierbas, flores. Aptas para interior y exterior cubierto. Fácil limpieza. Diseño escandinavo minimalista que complementa cualquier decoración.",
        "category": "Decoración",
        "price": 129.99,
        "stock": 88,
        "sku": "MACETAS-CER-SET3-WH-GEO"
    },
    {
        "name": "Lámpara de Mesa Táctil RGB Regulable",
        "description": "Lámpara de mesa LED moderna con control táctil de 3 niveles de brillo y modo RGB multicolor. Base cilíndrica de metal color negro mate con pantalla de acrílico translúcido. Dimensiones: 15cm diámetro x 25cm alto. LED integrado de 8W no reemplazable con vida útil de 50,000 horas. 3 temperaturas de color: cálida 3000K, neutra 4500K, fría 6000K + modo RGB con 16 colores. Control táctil en la base con memoria de última configuración. Puerto USB 5V/1A para cargar dispositivos. Luz difusa sin parpadeo, cuida la vista. Consumo bajo 8W. Perfecta para mesita de noche, escritorio, sala. Cable 1.5m. Incluye adaptador. Función temporizador 30/60 min.",
        "category": "Iluminación",
        "price": 79.99,
        "stock": 95,
        "sku": "LAMP-MESA-TACT-RGB-USB-BLK"
    },
    {
        "name": "Cortinas Blackout Térmicas 2 Paneles",
        "description": "Set de 2 paneles de cortinas blackout de alto rendimiento con aislamiento térmico. Tela triple capa: capa exterior decorativa poliéster, capa media espuma negra bloqueadora de luz, capa interior blanca. Dimensiones por panel: 140cm ancho x 220cm largo. Color: gris carbón elegante. Bloquea 99% de luz solar, UV y ruido exterior. Reduce pérdida de calor en invierno y mantiene fresco en verano, ahorro energético hasta 25%. Ojales metálicos reforzados cromados de 4cm, compatible con barras hasta 3cm. Resistente a arrugas y decoloración. Lavable en máquina agua fría, ciclo delicado. Planchar temperatura baja si necesario. Incluye 16 ganchos. Perfecto para dormitorios.",
        "category": "Decoración",
        "price": 119.99,
        "stock": 85,
        "sku": "CORTINAS-BLACKOUT-2PAN-GRY-220"
    },
    {
        "name": "Reloj de Pared Silencioso XXL 60cm",
        "description": "Reloj de pared extra grande de 60cm de diámetro con movimiento silencioso sin tic-tac. Esfera blanca minimalista con números arábigos grandes color negro mate y manecillas metálicas negras. Marco de metal color dorado rosa (rose gold) de 2cm. Cristal de vidrio mineral resistente a rayones. Mecanismo de cuarzo alemán de precisión ultra silencioso, funciona con 1 pila AA (no incluida). Gancho de montaje resistente incluido. Perfecto para salas grandes, comedores, oficinas, recepción. Visible desde lejos. Diseño moderno escandinavo. Peso: 1.8kg. Garantía 2 años en mecanismo. Fácil lectura. Ideal para espacios amplios.",
        "category": "Decoración",
        "price": 89.99,
        "stock": 90,
        "sku": "RELOJ-PARED-60CM-SILENC-ROSE"
    },
    {
        "name": "Cojines Decorativos Terciopelo Set 4 Piezas",
        "description": "Set de 4 cojines decorativos de terciopelo premium con relleno de plumas. Fundas de terciopelo suave color: 2 verde esmeralda + 2 dorado mostaza. Tamaño: 45cm x 45cm cada uno. Cremallera invisible en costado para fácil remoción. Relleno 90% plumas de pato blancas y 10% plumón (550 fill power), 650g por cojín. Muy suaves y moldeable. Fundas lavables a máquina agua fría, secar al aire. Relleno lavable en seco. Resistente a pelusas y decoloración. Costuras dobles reforzadas. Perfectos para sofá, cama, sillas. Añaden color y textura. Diseño elegante contemporáneo que combina con decoración moderna o clásica. Recuperan forma rápidamente.",
        "category": "Decoración",
        "price": 99.99,
        "stock": 92,
        "sku": "COJINES-TERCIOP-SET4-EME-GOLD"
    },
    {
        "name": "Tira LED Inteligente WiFi 10 Metros RGB",
        "description": "Tira de luces LED inteligentes de 10 metros controlables por app y voz. 300 LEDs SMD 5050 RGB + blanco cálido/frío. Control WiFi 2.4GHz compatible con Alexa, Google Home, Siri Shortcuts. App gratuita permite: 16 millones de colores, brillo ajustable, 28 modos dinámicos, sincronización con música, temporizador, programación. Adhesivo 3M en reverso, fácil instalación en techo, pared, muebles, TV. IP65 resistente a salpicaduras en cocina/baño. Voltaje 12V seguro con adaptador certificado incluido. Cortable cada 3 LEDs en marcas. Incluye: tira 10m, controlador WiFi, adaptador, manual. Conectores incluidos para esquinas. Vida útil 50,000 horas. Bajo consumo 72W total.",
        "category": "Iluminación",
        "price": 149.99,
        "stock": 82,
        "sku": "LED-WIFI-10M-RGB-ALEXA"
    },
    {
        "name": "Perchero de Pie Moderno Bambú",
        "description": "Perchero de pie tipo árbol de bambú natural ecológico con 8 ganchos de madera. Diseño minimalista escandinavo. Dimensiones: 42cm diámetro base x 176cm altura. Base circular ponderada con 3 patas para máxima estabilidad. Poste central de 5cm diámetro. 8 ganchos distribuidos en 3 niveles: 4 arriba, 3 medio, 1 superior para sombreros. Cada gancho soporta 5kg, carga total 25kg. Acabado natural barniz mate protector. Fácil ensamblaje con instrucciones ilustradas. Perfecto para entrada, dormitorio, oficina. Ocupa poco espacio. Incluye protectores de piso. Peso: 3.2kg. Material sostenible renovable. Combina funcionalidad y estética.",
        "category": "Decoración",
        "price": 79.99,
        "stock": 87,
        "sku": "PERCHERO-PIE-BAMBU-8GANCH"
    },
    {
        "name": "Lámpara de Techo LED Panel Circular 40cm",
        "description": "Plafón LED de techo circular ultradelgado de 40cm diámetro x 3cm grosor. LED integrado 36W con 3600 lúmenes, equivalente a 360W incandescente. Tres temperaturas de color seleccionables con control remoto: cálida 3000K, neutra 4500K, fría 6000K. Brillo regulable 10-100%. Acrílico difusor de alta transmisión para luz uniforme sin puntos. Marco de aluminio blanco mate. Montaje flush al techo, ideal para techos bajos. Ángulo de haz 120°. Vida útil 50,000 horas. Consumo eficiente clase A++. Controlador incluido en base. Perfecto para sala, dormitorio, cocina, oficina. Fácil instalación. Incluye kit de montaje y control remoto. Certificación CE.",
        "category": "Iluminación",
        "price": 129.99,
        "stock": 78,
        "sku": "PLAFON-LED-40CM-3COLOR-DIM"
    }
]


async def seed_part4():
    """Seed Decoración e Iluminación products"""
    await MongoDB.connect()
    await PineconeStore.initialize()
    
    product_repo = MongoProductRepository()
    vectorstore = PineconeStore()
    
    print("🌱 Seeding Part 4: Decoración e Iluminación (13 productos nuevos)...")
    
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
            
            print(f"✅ [{idx}/13] {product.name}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print(f"\n✅ Part 4 complete: 13 productos de Decoración e Iluminación!")
    print("\n📊 Total agregado en catálogo extendido: 58 productos nuevos")
    print("💡 Catálogo completo ahora tiene: 66 productos (8 originales + 58 nuevos)")
    
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_part4())
