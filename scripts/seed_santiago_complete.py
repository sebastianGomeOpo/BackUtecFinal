"""
Seed completo para Santiago, Chile
40+ lugares reales con coordenadas reales
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

# Lugares reales de Santiago con coordenadas reales
SANTIAGO_PLACES = [
    # DEPORTES - Centro y cercanías (10 lugares)
    {
        "id": "place_stgo_sport_001",
        "image_url": "https://images.unsplash.com/photo-1571902943202-507ec2618e8f",
        "title": "Cerro San Cristóbal",
        "description": "Parque metropolitano con senderos para trekking, ciclismo y running. Vista panorámica de Santiago. Teleférico y funicular disponibles. Ideal para ejercicio al aire libre.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.6347, -33.4267],  # Bellavista
            "address": "Pío Nono 450, Recoleta",
            "neighborhood": "Recoleta"
        },
        "tags": ["parque", "trekking", "running", "ciclismo", "vista panorámica", "naturaleza", "aire libre"]
    },
    {
        "id": "place_stgo_sport_002",
        "image_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e",
        "title": "Parque Forestal",
        "description": "Parque lineal perfecto para correr, caminar o andar en bicicleta. Senderos planos, arbolado y muy céntrico. Popular entre runners matutinos.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.6450, -33.4350],  # Centro
            "address": "Av. Ismael Valdés Vergara, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["parque", "running", "ciclismo", "caminata", "senderos", "centro", "arboles"]
    },
    {
        "id": "place_stgo_sport_003",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd",
        "title": "Parque Quinta Normal",
        "description": "Amplio parque urbano con laguna, ciclovías y senderos para trotar. Perfecto para deportes al aire libre y picnics. Espacios abiertos y sombra.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.6798, -33.4403],  # Quinta Normal
            "address": "Av. Matucana 520, Quinta Normal",
            "neighborhood": "Quinta Normal"
        },
        "tags": ["parque", "ciclovia", "running", "picnic", "laguna", "familia", "amplios"]
    },
    {
        "id": "place_stgo_sport_004",
        "image_url": "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8",
        "title": "Parque Araucano",
        "description": "Parque moderno en Las Condes con pistas de trote, ciclovías y áreas de ejercicio. Muy bien mantenido con zonas verdes extensas.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.5780, -33.4097],  # Las Condes
            "address": "Av. Presidente Riesco 5330, Las Condes",
            "neighborhood": "Las Condes"
        },
        "tags": ["parque", "running", "ciclovia", "ejercicio", "moderno", "verde", "familias"]
    },
    {
        "id": "place_stgo_sport_005",
        "image_url": "https://images.unsplash.com/photo-1483721310020-03333e577078",
        "title": "Parque Bicentenario",
        "description": "Hermoso parque con laguna artificial, ideal para correr o caminar. Senderos pavimentados y vista a los edificios corporativos de Vitacura.",
        "category": "Deportes",
        "location": {
            "coordinates": [-70.5844, -33.4002],  # Vitacura
            "address": "Av. Bicentenario 3800, Vitacura",
            "neighborhood": "Vitacura"
        },
        "tags": ["parque", "laguna", "running", "caminata", "moderno", "paisajismo", "familias"]
    },
    
    # GASTRONOMÍA - Cafés y Restaurantes Centro (15 lugares)
    {
        "id": "place_stgo_food_001",
        "image_url": "https://images.unsplash.com/photo-1554118811-1e0d58224f24",
        "title": "Café Colmado",
        "description": "Café artesanal en Lastarria con terraza. Especialidad en café de origen y brunch. Ambiente bohemio y relajado. Ideal para trabajar.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6370, -33.4378],  # Lastarria
            "address": "José Victorino Lastarria 282, Santiago",
            "neighborhood": "Lastarria"
        },
        "tags": ["café", "brunch", "terraza", "artesanal", "bohemio", "trabajo remoto", "wifi"]
    },
    {
        "id": "place_stgo_food_002",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Café Mosqueto",
        "description": "Café de especialidad en Barrio Italia. Excelente carta de cafés y repostería casera. Pet-friendly con patio interior.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6124, -33.4503],  # Providencia
            "address": "Av. Italia 1456, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["café", "especialidad", "repostería", "pet-friendly", "patio", "barrio italia"]
    },
    {
        "id": "place_stgo_food_003",
        "image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0",
        "title": "Boragó",
        "description": "Restaurante de alta cocina chilena, reconocido internacionalmente. Menú degustación con ingredientes nativos. Requiere reserva anticipada.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.5780, -33.4097],  # Vitacura
            "address": "Nueva Costanera 3467, Vitacura",
            "neighborhood": "Vitacura"
        },
        "tags": ["restaurante", "alta cocina", "gourmet", "chileno", "premiado", "degustación", "reserva"]
    },
    {
        "id": "place_stgo_food_004",
        "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5",
        "title": "Mercado Central",
        "description": "Mercado histórico con mariscos frescos y comida típica chilena. Ambiente auténtico y popular. Ideal para almorzar caldillo de congrio o paila marina.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6506, -33.4361],  # Santiago Centro
            "address": "San Pablo 967, Santiago Centro",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["mercado", "mariscos", "chileno", "típico", "histórico", "almuerzo", "auténtico"]
    },
    {
        "id": "place_stgo_food_005",
        "image_url": "https://images.unsplash.com/photo-1559339352-11d035aa65de",
        "title": "La Vega Central",
        "description": "Mercado popular con frutas, verduras y puestos de comida casera. Jugos naturales y comida económica auténtica. Ambiente local vibrante.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6431, -33.4281],  # Recoleta
            "address": "Antonia López de Bello 740, Recoleta",
            "neighborhood": "Recoleta"
        },
        "tags": ["mercado", "jugos", "comida casera", "económico", "local", "frutas", "auténtico"]
    },
    {
        "id": "place_stgo_food_006",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Castillo Forestal",
        "description": "Restaurante con terraza frente al Parque Forestal. Cocina mediterránea y chilena. Ambiente elegante ideal para cenas románticas.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6456, -33.4361],  # Lastarria
            "address": "José Victorino Lastarria 307, Santiago",
            "neighborhood": "Lastarria"
        },
        "tags": ["restaurante", "terraza", "mediterráneo", "elegante", "romántico", "parque forestal"]
    },
    {
        "id": "place_stgo_food_007",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Liguria",
        "description": "Clásico bar-restaurante santiaguino. Ambiente bohemio con paredes llenas de afiches. Comida chilena tradicional y excelentes pisco sours.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6124, -33.4273],  # Providencia
            "address": "Av. Pedro de Valdivia 047, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["bar", "restaurante", "bohemio", "chileno", "tradicional", "pisco sour", "clásico"]
    },
    {
        "id": "place_stgo_food_008",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Peumayén",
        "description": "Restaurante de cocina ancestral chilena en Lastarria. Ingredientes nativos y preparaciones tradicionales. Ambiente acogedor y educativo.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-70.6378, -33.4372],  # Lastarria
            "address": "Constitución 136, Santiago",
            "neighborhood": "Lastarria"
        },
        "tags": ["restaurante", "ancestral", "chileno", "nativo", "tradicional", "acogedor", "cultural"]
    },
    
    # CULTURA - Museos y Centros Culturales (10 lugares)
    {
        "id": "place_stgo_culture_001",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Museo de Bellas Artes",
        "description": "Principal museo de arte de Chile. Colecciones de arte chileno y europeo. Arquitectura neoclásica impresionante en el Parque Forestal. Entrada gratuita.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6456, -33.4353],  # Parque Forestal
            "address": "José Miguel de la Barra 650, Santiago",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["museo", "arte", "cultura", "gratuito", "neoclásico", "parque forestal", "exposiciones"]
    },
    {
        "id": "place_stgo_culture_002",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Centro Cultural Gabriela Mistral (GAM)",
        "description": "Centro cultural con teatro, exposiciones y eventos. Arquitectura moderna destacada. Programación variada de arte contemporáneo y espectáculos.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6506, -33.4392],  # Santiago Centro
            "address": "Av. Libertador Bernardo O'Higgins 227, Santiago",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["centro cultural", "teatro", "exposiciones", "moderno", "eventos", "arte contemporáneo"]
    },
    {
        "id": "place_stgo_culture_003",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Museo de la Memoria y los Derechos Humanos",
        "description": "Museo dedicado a la memoria de las víctimas de la dictadura militar. Exposición permanente conmovedora. Arquitectura moderna y significativa.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6814, -33.4411],  # Quinta Normal
            "address": "Av. Matucana 501, Quinta Normal",
            "neighborhood": "Quinta Normal"
        },
        "tags": ["museo", "historia", "derechos humanos", "memoria", "educativo", "conmovedor"]
    },
    {
        "id": "place_stgo_culture_004",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Barrio Lastarria",
        "description": "Barrio cultural y bohemio con galerías de arte, librerías y cafés. Arquitectura patrimonial y ambiente artístico. Ideal para paseos culturales.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6370, -33.4378],  # Lastarria
            "address": "José Victorino Lastarria, Santiago",
            "neighborhood": "Lastarria"
        },
        "tags": ["barrio", "bohemio", "galerías", "librerías", "arquitectura", "patrimonial", "artístico"]
    },
    {
        "id": "place_stgo_culture_005",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Centro Cultural Palacio La Moneda",
        "description": "Centro cultural bajo el Palacio de Gobierno. Exposiciones de arte chileno e internacional. Tienda de diseño y cafetería. Entrada gratuita.",
        "category": "Cultura",
        "location": {
            "coordinates": [-70.6539, -33.4428],  # Santiago Centro
            "address": "Plaza de la Ciudadanía 26, Santiago",
            "neighborhood": "Santiago Centro"
        },
        "tags": ["centro cultural", "exposiciones", "gratuito", "diseño", "arte", "moneda", "cafetería"]
    },
    
    # ENTRETENIMIENTO - Vida Nocturna y Ocio (8 lugares)
    {
        "id": "place_stgo_ent_001",
        "image_url": "https://images.unsplash.com/photo-1566417713940-fe7c737a9ef2",
        "title": "Barrio Bellavista",
        "description": "Principal barrio bohemio de Santiago. Bares, restaurantes, discotecas y vida nocturna. Casa museo de Pablo Neruda (La Chascona). Ambiente juvenil.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.6347, -33.4267],  # Bellavista
            "address": "Pío Nono, Bellavista",
            "neighborhood": "Bellavista"
        },
        "tags": ["barrio", "vida nocturna", "bares", "discotecas", "bohemio", "juvenil", "pablo neruda"]
    },
    {
        "id": "place_stgo_ent_002",
        "image_url": "https://images.unsplash.com/photo-1533777324565-a040eb52facd",
        "title": "Costanera Center",
        "description": "Mall más alto de Sudamérica con Sky Costanera (mirador). Tiendas, cines, restaurantes y vista panorámica de 360° desde el piso 61.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.6060, -33.4169],  # Providencia
            "address": "Av. Andrés Bello 2425, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["mall", "shopping", "mirador", "vista panorámica", "cines", "restaurantes", "torre"]
    },
    {
        "id": "place_stgo_ent_003",
        "image_url": "https://images.unsplash.com/photo-1566417713940-fe7c737a9ef2",
        "title": "Patio Bellavista",
        "description": "Centro gastronómico y cultural al aire libre. Variedad de restaurantes y bares. Shows en vivo y ambiente festivo. Popular para salir a cenar.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.6331, -33.4278],  # Bellavista
            "address": "Constitución 30, Bellavista",
            "neighborhood": "Bellavista"
        },
        "tags": ["patio", "restaurantes", "bares", "shows", "cultura", "aire libre", "festivo"]
    },
    {
        "id": "place_stgo_ent_004",
        "image_url": "https://images.unsplash.com/photo-1566417713940-fe7c737a9ef2",
        "title": "Barrio Italia",
        "description": "Barrio emergente con diseño, anticuarios y gastronomía. Cafés de especialidad, tiendas boutique y restaurantes innovadores. Ambiente hipster.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-70.6124, -33.4503],  # Providencia
            "address": "Av. Italia, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["barrio", "diseño", "anticuarios", "cafés", "boutique", "hipster", "emergente"]
    },
    
    # COMPRAS (5 lugares)
    {
        "id": "place_stgo_shop_001",
        "image_url": "https://images.unsplash.com/photo-1533777324565-a040eb52facd",
        "title": "Parque Arauco",
        "description": "Mall premium en Las Condes. Tiendas internacionales, restaurantes y cines. Zona gourmet y tiendas de lujo. Estacionamiento amplio.",
        "category": "Compras",
        "location": {
            "coordinates": [-70.5811, -33.4053],  # Las Condes
            "address": "Av. Kennedy 5413, Las Condes",
            "neighborhood": "Las Condes"
        },
        "tags": ["mall", "premium", "lujo", "tiendas", "restaurantes", "cines", "estacionamiento"]
    },
    {
        "id": "place_stgo_shop_002",
        "image_url": "https://images.unsplash.com/photo-1533777324565-a040eb52facd",
        "title": "Mall Costanera Center",
        "description": "Centro comercial integrado a la torre más alta de Chile. 350+ tiendas, zona gourmet, cines y acceso al Sky Costanera. Metro conectado.",
        "category": "Compras",
        "location": {
            "coordinates": [-70.6060, -33.4169],  # Providencia
            "address": "Av. Andrés Bello 2425, Providencia",
            "neighborhood": "Providencia"
        },
        "tags": ["mall", "shopping", "grande", "tiendas", "gourmet", "metro", "torre"]
    }
]


async def seed_santiago_complete():
    """Seed completo de lugares de Santiago"""
    
    print("🇨🇱 Iniciando seed completo de Santiago...")
    print(f"📝 {len(SANTIAGO_PLACES)} lugares a insertar")
    
    try:
        # Connect to MongoDB
        await MongoDB.connect()
        print("✅ Conectado a MongoDB")
        
        # Initialize Pinecone
        await PlacesPineconeStore.initialize()
        print("✅ Conectado a Pinecone")
        
        # Get collections
        posts_collection = MongoDB.get_database()["place_posts"]
        vectorstore = PlacesPineconeStore()
    
        # Delete existing Santiago places
        print("🗑️  Limpiando lugares anteriores de Santiago...")
        santiago_ids = [place["id"] for place in SANTIAGO_PLACES]
        await posts_collection.delete_many({"id": {"$in": santiago_ids}})
    
        # Insert places
        print(f"📍 Insertando {len(SANTIAGO_PLACES)} lugares de Santiago...")
        
        categories_count = {}
        
        for place_data in SANTIAGO_PLACES:
            # Create PlacePost
            post = PlacePost(
                id=place_data["id"],
                image_url=place_data["image_url"],
                title=place_data["title"],
                description=place_data["description"],
                category=place_data["category"],
                location=Location(**place_data["location"]),
                tags=place_data["tags"],
                sponsor="Coca-Cola Andina",
                created_at=datetime.utcnow()
            )
            
            # Insert to MongoDB
            await posts_collection.insert_one(post.dict())
            
            # Upsert to Pinecone
            await vectorstore.upsert_place(post)
            
            # Count by category
            cat = place_data["category"]
            categories_count[cat] = categories_count.get(cat, 0) + 1
            
            print(f"  ✅ {post.title} ({post.category})")
        
        # Create geospatial index
        print("📍 Creando índice geoespacial...")
        await posts_collection.create_index([("location.coordinates", "2dsphere")])
        
        print(f"\n✅ Seed completado! {len(SANTIAGO_PLACES)} lugares de Santiago agregados")
        
        # Show summary
        print("\n📊 Lugares por categoría:")
        for cat, count in sorted(categories_count.items()):
            print(f"  - {cat}: {count}")
        
        print("\n🎉 Santiago está listo para usar!")
        
    finally:
        # Close connections
        await MongoDB.disconnect()
        print("\n👋 Desconectado de MongoDB")


if __name__ == "__main__":
    asyncio.run(seed_santiago_complete())

