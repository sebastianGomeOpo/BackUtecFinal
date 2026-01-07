"""
Seed Part 3: Cocina y Electrodomésticos (15 productos)
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
        "name": "Set de Ollas Antiadherentes Premium 12 Piezas",
        "description": "Juego completo de batería de cocina de 12 piezas con recubrimiento antiadherente de cerámica titanio reforzado libre de PFOA, PTFE y metales pesados. Incluye: ollas 18cm/2L, 20cm/3L, 24cm/5L con tapas de vidrio templado, sartenes 20cm, 24cm, 28cm, cazo 16cm con tapa, y 3 utensilios de nylon (espátula, cuchara, espumadera). Base de aluminio forjado con difusor térmico multicapa para distribución uniforme. Mangos de baquelita ergonómicos resistentes al calor. Apto para todas las cocinas: gas, eléctrica, vitrocerámica e inducción. Apto lavavajillas. Color negro mate exterior, interior beige antiadherente. Garantía 5 años.",
        "category": "Cocina",
        "price": 299.99,
        "stock": 70,
        "sku": "OLLAS-SET-12P-CER-TI"
    },
    {
        "name": "Juego de Cuchillos Profesionales 15 Piezas con Bloque",
        "description": "Set profesional de 15 cuchillos de acero inoxidable alemán de alto carbono (X50CrMoV15). Incluye: cuchillo chef 20cm, cuchillo pan 20cm, cuchillo trinchar 20cm, cuchillo santoku 18cm, cuchillo utili dad 13cm, cuchillo pelar 9cm, 6 cuchillos bistec, tijeras multiuso, afilador manual y bloque de madera de bambú con diseño moderno. Hojas forjadas con filo láser, dureza HRC 56-58. Mangos ergonómicos triple remache color negro. Balance perfecto. Resistentes a corrosión y óxido. Afilado profesional incluido. Lavado a mano recomendado.",
        "category": "Cocina",
        "price": 249.99,
        "stock": 65,
        "sku": "CUCHILLOS-PRO-15P-ALEM"
    },
    {
        "name": "Procesador de Alimentos Multifuncional 1200W",
        "description": "Procesador de alimentos de alta potencia 1200W con motor de cobre puro y 12 funciones. Incluye: bowl principal 3.5L de acero inoxidable, picadora 2L vidrio, licuadora 1.8L con 6 velocidades + pulse. Accesorios: disco rebanador reversible, disco rallador fino/grueso, batidor de varillas, amasador, espátula. Panel de control digital con pantalla LED. 12 velocidades programables. Base antideslizante con ventosas. Cuchillas de acero inoxidable japonés. Sistema de seguridad con bloqueo. Libre de BPA. Motor silencioso. Incluye recetario. Color plateado/negro. Garantía 2 años.",
        "category": "Electrodomésticos",
        "price": 349.99,
        "stock": 58,
        "sku": "PROC-ALIM-1200W-12F"
    },
    {
        "name": "Licuadora de Alta Potencia 2000W Profesional",
        "description": "Licuadora profesional de 2000W con motor industrial y 6 cuchillas de acero inoxidable titanio. Jarra Tritan de 2 litros libre de BPA, resistente a impactos y altas temperaturas (hasta 100°C). 10 velocidades variables + función pulse + 8 programas preestablecidos (smoothie, hielo, sopas calientes, purés, limpieza automática). Pantalla táctil LED. Cuchillas extraíbles para fácil limpieza. Base de aleación de zinc extra pesada (3.5kg) para máxima estabilidad. Pica hielo en segundos. Incluye libro de 100 recetas y tamper. Color negro mate. Garantía 3 años.",
        "category": "Electrodomésticos",
        "price": 449.99,
        "stock": 62,
        "sku": "LICUADORA-2000W-PRO-BLK"
    },
    {
        "name": "Cafetera Express Espresso 20 Bares",
        "description": "Cafetera espresso profesional con bomba italiana de 20 bares de presión para extracción perfecta. Sistema de calentamiento Thermoblock que alcanza temperatura óptima en 30 segundos. Vaporizador profesional ajustable para espuma de leche. Capacidad del tanque: 1.5 litros removible. Portafiltro de acero inoxidable para café molido y compatible con cápsulas ESE. Panel de control con 3 temperaturas y presión programable. Incluye: tamper, cucharón dosificador, 2 tazas espresso de vidrio. Bandeja antigoteo removible. Estructura de acero inoxidable cepillado. Potencia 1450W. Dimensiones: 33x30x31cm. Garantía 2 años.",
        "category": "Electrodomésticos",
        "price": 599.99,
        "stock": 54,
        "sku": "CAFETERA-ESP-20BAR-SS"
    },
    {
        "name": "Vajilla de Porcelana 30 Piezas Servicio 6 Personas",
        "description": "Juego completo de vajilla de porcelana bone china premium para 6 personas (30 piezas). Incluye por persona: plato base 27cm, plato hondo 22cm, plato postre 20cm, taza 250ml con platillo. Diseño elegante con borde dorado y patrón floral delicado color marfil. Porcelana de alta calidad con translucidez característica, resistente a astillas y rayones. Esmalte vitrificado que conserva brillo. Apta para microondas y lavavajillas. Apilable para ahorro de espacio. Incluye caja de regalo. Perfecta para uso diario o eventos especiales. Certificado FDA.",
        "category": "Cocina",
        "price": 279.99,
        "stock": 72,
        "sku": "VAJILLA-PORC-30P-6PERS-ORO"
    },
    {
        "name": "Freidora de Aire 6.5L Digital Sin Aceite",
        "description": "Freidora de aire de gran capacidad 6.5 litros con tecnología de circulación de aire caliente 360° Rapid Air. Potencia 1700W. Panel digital táctil con 8 programas preestablecidos: papas, pollo, camarones, carne, pescado, pizza, postre, vegetales. Temperatura ajustable 80-200°C, temporizador hasta 60 minutos con apagado automático. Canasta antiadherente con recubrimiento cerámico, removible y apta lavavajillas. Capacidad para alimentar 4-6 personas. Ventana de visualización con luz LED interna. Cocción hasta 85% menos grasa. Incluye recetario con 50 recetas. Protección contra sobrecalentamiento. Color negro. Dimensiones: 35x32x33cm.",
        "category": "Electrodomésticos",
        "price": 229.99,
        "stock": 88,
        "sku": "FREIDORA-AIRE-6.5L-DIG"
    },
    {
        "name": "Juego de Cubiertos 72 Piezas Acero Inoxidable 18/10",
        "description": "Set de cubertería de lujo de 72 piezas en acero inoxidable 18/10 grado premium para 12 personas. Incluye por persona: tenedor mesa, cuchillo mesa, cuchara mesa, tenedor postre, cuchara postre, cuchara té. Diseño elegante tipo hotel con patrón clásico y acabado espejo pulido. Peso balanceado perfecto. Mangos sólidos sin costuras. Resistente a corrosión, óxido y decoloración. No retiene olores ni sabores. Apto lavavajillas. Espesor 2.5mm. Incluye estuche elegante de madera con forro de terciopelo. Perfecto para banquetes y uso diario. Garantía de por vida contra defectos.",
        "category": "Cocina",
        "price": 199.99,
        "stock": 75,
        "sku": "CUBIERTOS-72P-SS1810-ESPE"
    },
    {
        "name": "Horno Microondas Digital 28L 1000W",
        "description": "Microondas digital multifuncional de 28 litros con 1000W de potencia. 10 niveles de potencia ajustables + 8 menús automáticos (palomitas, pizza, vegetales, pescado, carne, papa, bebidas, descongelar por peso/tiempo). Panel de control digital con pantalla LED grande. Plato giratorio de vidrio 31.5cm. Interior de acero inoxidable fácil de limpiar. Función express 30 segundos. Reloj y temporizador hasta 95 minutos. Bloqueo infantil. Cocción uniforme con distribución homogénea de microondas. Acabado negro con espejo y manija integrada. Dimensiones: 48x37x28cm. Potencia cocción/grill. Bajo consumo energético.",
        "category": "Electrodomésticos",
        "price": 179.99,
        "stock": 80,
        "sku": "MICRO-28L-1000W-DIG-BLK"
    },
    {
        "name": "Tabla de Cortar de Bambú 3 Tamaños con Soporte",
        "description": "Set de 3 tablas de cortar de bambú ecológico de primera calidad con soporte de acero inoxidable. Tamaños: Grande 40x30x2cm, Mediana 35x25x1.5cm, Pequeña 25x18x1cm. Bambú orgánico tratado con aceite mineral grado alimenticio. Superficie lisa que no daña cuchillos. Naturalmente antibacteriano y antimicrobiano. Canal perimetral para jugos en tabla grande. Asas ergonómicas con agujero para colgar. Más duro que madera tradicional pero gentil con filos. No absorbe olores ni humedad. Reversibles. Incluye soporte organizador moderno. Mantenimiento fácil: lavar con agua y jabón, secar inmediatamente. Aceite de mantenimiento incluido.",
        "category": "Cocina",
        "price": 79.99,
        "stock": 95,
        "sku": "TABLA-CORTAR-BAMBU-3PZ-SOP"
    },
    {
        "name": "Batidora de Mano Inalámbrica 500W 5 Velocidades",
        "description": "Batidora de mano inalámbrica recargable con motor de 500W y batería de litio de 2500mAh. 5 velocidades + turbo. Autonomía hasta 40 minutos de uso continuo. Carga completa en 3 horas con base de carga incluida. Cuerpo ergonómico de acero inoxidable con agarre soft-touch antideslizante. Incluye: batidor de varillas desmontable, accesorio picador 500ml, vaso medidor 700ml graduado, batidor globo para claras. Pie desmontable de acero para fácil limpieza, apto lavavajillas. Sistema anti-salpicaduras. Indicador LED de batería y velocidad. Libre de cables durante uso. Color plateado/negro. Garantía 18 meses.",
        "category": "Electrodomésticos",
        "price": 129.99,
        "stock": 82,
        "sku": "BATIDORA-INAL-500W-5V-LITH"
    },
    {
        "name": "Set de Recipientes Herméticos Vidrio 18 Piezas",
        "description": "Juego de 18 piezas de recipientes de almacenamiento de vidrio borosilicato (9 envases + 9 tapas). Resistente a cambios térmicos -20°C a 400°C. Tamaños variados: 3x370ml, 3x640ml, 3x1040ml redondos y rectangulares. Tapas herméticas de plástico PP libre de BPA con 4 cierres de seguridad y anillo de silicona. Apto para microondas (sin tapa), horno, congelador y lavavajillas. Vidrio transparente para fácil identificación. No absorbe olores ni colores. Apilables para ahorrar espacio. Perfecto para meal prep, almacenar sobras, lunch box. Incluye etiquetas reutilizables y marcador. Garantía de por vida en vidrio.",
        "category": "Cocina",
        "price": 99.99,
        "stock": 90,
        "sku": "RECIPIENTES-VID-18PZ-HERM"
    },
    {
        "name": "Sandwichera Grill y Waflera 3 en 1",
        "description": "Sandwichera multifuncional 3 en 1 con placas intercambiables: grill liso, grill acanalado tipo parrilla y waflera belga. Potencia 1200W para calentamiento rápido y cocción uniforme. Placas antiadherentes removibles de aluminio fundido, aptas lavavajillas. Indicadores LED de encendido y temperatura lista. Termostato automático. Apertura 180° para usar como plancha. Superficie de cocción: 28x23cm. Mangos de toque frío. Bandeja recolectora de grasa removible. Capacidad: 2-4 sandwiches o 4 wafles belgas. Cable giratorio. Incluye recetario. Color negro/plateado. Dimensiones cerrada: 33x27x10cm. Sistema de cierre con traba.",
        "category": "Electrodomésticos",
        "price": 89.99,
        "stock": 85,
        "sku": "SANDWICHERA-3EN1-WAFL-1200W"
    },
    {
        "name": "Extractor de Jugos Slow Juicer Prensado en Frío",
        "description": "Extractor de jugos de prensado lento (slow juicer) con tecnología de masticación a 80 RPM que preserva nutrientes, enzimas y vitaminas. Motor silencioso de 250W con sistema de reducción inversa anti-atascos. Barrena de una sola pieza con 7 segmentos de trituración. Tubo de alimentación XL 8cm para frutas enteras. Jarra de jugo 1L y contenedor de pulpa 1L libre de BPA. Filtro fino de acero inoxidable para jugo sin pulpa. Extracción en frío sin oxidación, jugos duran hasta 72 horas. Fácil limpieza con cepillo incluido. Todas las piezas desmontables aptas lavavajillas. Base estable con ventosas. Color gris/negro. Incluye recetario detox. Garantía 3 años motor.",
        "category": "Electrodomésticos",
        "price": 379.99,
        "stock": 60,
        "sku": "EXTRACTOR-SLOW-JUICER-80RPM"
    },
    {
        "name": "Juego de Sartenes Cerámica 3 Piezas Colores",
        "description": "Set de 3 sartenes de aluminio forjado con recubrimiento cerámico Whitford Thermolon de última generación, ecológico y libre de PFAS, PFOA, plomo y cadmio. Tamaños: 20cm, 24cm, 28cm. Colores degradados: turquesa, coral y lavanda. Base de inducción con disco encapsulado de acero inoxidable para calentamiento rápido y uniforme. Mangos ergonómicos de baquelita con sistema stay-cool. Antiadherentes superiores que requieren mínimo aceite. Resistentes a 450°C en horno. Compatibles con todas las fuentes de calor. Fácil limpieza, aptas lavavajillas. Espesor 3mm. Perfectas para tortillas, salteados, carnes. Embalaje ecológico.",
        "category": "Cocina",
        "price": 159.99,
        "stock": 78,
        "sku": "SARTENES-CER-3PZ-COLOR-IND"
    }
]


async def seed_part3():
    """Seed Cocina y Electrodomésticos products"""
    await MongoDB.connect()
    await PineconeStore.initialize()
    
    product_repo = MongoProductRepository()
    vectorstore = PineconeStore()
    
    print("🌱 Seeding Part 3: Cocina y Electrodomésticos (15 productos)...")
    
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
    
    print(f"\n✅ Part 3 complete: 15 productos de Cocina y Electrodomésticos!")
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_part3())
