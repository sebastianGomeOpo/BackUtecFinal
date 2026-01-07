"""
Seed script for Lima, Peru places
Adds 10 places in Lima with various categories
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

# Lima, Peru places
LIMA_PLACES = [
    {
        "id": "place_lima_001",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Café del Parque",
        "description": "Café acogedor con terraza al aire libre en el Parque Kennedy. Ideal para trabajar o tomar un café tranquilo. Tienen excelentes sándwiches, ensaladas y postres caseros. WiFi gratis y ambiente relajado.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0282, -12.1191],  # Miraflores - Parque Kennedy
            "address": "Av. Oscar R. Benavides 290, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["café", "terraza", "al aire libre", "wifi", "trabajo remoto", "parque kennedy"]
    },
    {
        "id": "place_lima_002",
        "image_url": "https://images.unsplash.com/photo-1559339352-11d035aa65de",
        "title": "Cevichería La Mar",
        "description": "Restaurante de comida marina peruana con los mejores ceviches de Lima. Ambiente moderno y fresco. Especialidad en pescados y mariscos del día. Terraza amplia con vista al mar.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0365, -12.1249],  # Miraflores - cerca al malecón
            "address": "Av. La Mar 770, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["ceviche", "comida peruana", "mariscos", "restaurante", "terraza", "vista al mar"]
    },
    {
        "id": "place_lima_003",
        "image_url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa",
        "title": "Parque de la Reserva - Circuito Mágico del Agua",
        "description": "Complejo de piletas con espectáculo de agua, luces y música. Perfecto para ir en familia o con amigos. Show nocturno impresionante. Entrada económica.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-77.0344, -12.0702],  # Cercado de Lima
            "address": "Jr. Madre de Dios s/n, Cercado de Lima",
            "neighborhood": "Cercado de Lima"
        },
        "tags": ["parque", "fuentes de agua", "show nocturno", "familiar", "entretenimiento", "luces"]
    },
    {
        "id": "place_lima_004",
        "image_url": "https://images.unsplash.com/photo-1582037928769-181f2644ecb7",
        "title": "Museo Larco",
        "description": "Museo de arte precolombino con impresionante colección de cerámica, textiles y oro. Hermosos jardines y cafetería. Perfecto para conocer la historia del Perú antiguo.",
        "category": "Cultura",
        "location": {
            "coordinates": [-77.0707, -12.0714],  # Pueblo Libre
            "address": "Av. Bolívar 1515, Pueblo Libre",
            "neighborhood": "Pueblo Libre"
        },
        "tags": ["museo", "cultura", "arte precolombino", "historia", "jardines", "turismo"]
    },
    {
        "id": "place_lima_005",
        "image_url": "https://images.unsplash.com/photo-1466978913421-dad2ebd01d17",
        "title": "Malecón de Miraflores",
        "description": "Paseo costero con impresionantes vistas al océano Pacífico. Ideal para caminar, correr o andar en bicicleta. Parques, cafés y área para parapente. Atardeceres espectaculares.",
        "category": "Deportes",
        "location": {
            "coordinates": [-77.0420, -12.1296],  # Miraflores - Malecón
            "address": "Malecón Cisneros, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["malecón", "vista al mar", "deportes", "ciclismo", "running", "parapente", "atardecer"]
    },
    {
        "id": "place_lima_006",
        "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5",
        "title": "Barranco - Barrio Bohemio",
        "description": "Barrio artístico y cultural con galerías, murales callejeros, bares y restaurantes. Puente de los Suspiros icónico. Vida nocturna vibrante y ambiente bohemio.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-77.0208, -12.1464],  # Barranco
            "address": "Jr. Unión, Barranco",
            "neighborhood": "Barranco"
        },
        "tags": ["barranco", "arte", "bohemio", "bares", "vida nocturna", "puente de los suspiros", "murales"]
    },
    {
        "id": "place_lima_007",
        "image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0",
        "title": "Central Restaurante",
        "description": "Restaurante gourmet reconocido internacionalmente. Experiencia gastronómica única explorando los pisos altitudinales del Perú. Reserva con anticipación.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0208, -12.1464],  # Barranco
            "address": "Av. Pedro de Osma 301, Barranco",
            "neighborhood": "Barranco"
        },
        "tags": ["restaurante gourmet", "alta cocina", "experiencia culinaria", "reserva", "premiado"]
    },
    {
        "id": "place_lima_008",
        "image_url": "https://images.unsplash.com/photo-1533777324565-a040eb52facd",
        "title": "Larcomar",
        "description": "Centro comercial al aire libre con vista al océano. Tiendas, restaurantes, cines y entretenimiento. Perfecto para shopping y disfrutar la brisa marina.",
        "category": "Compras",
        "location": {
            "coordinates": [-77.0430, -12.1320],  # Miraflores - frente al mar
            "address": "Av. Malecón de la Reserva 610, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["shopping", "centro comercial", "vista al mar", "restaurantes", "cines", "tiendas"]
    },
    {
        "id": "place_lima_009",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Huaca Pucllana",
        "description": "Sitio arqueológico prehispánico en pleno Miraflores. Pirámide de adobe de la cultura Lima. Tours guiados y restaurante con vista a las ruinas iluminadas.",
        "category": "Cultura",
        "location": {
            "coordinates": [-77.0320, -12.1073],  # Miraflores
            "address": "Calle General Borgoño cuadra 8, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["arqueología", "huaca", "cultura lima", "ruinas", "tour", "historia prehispánica"]
    },
    {
        "id": "place_lima_010",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Café de la Paz",
        "description": "Café vegano y vegetariano en San Isidro. Comida saludable, jugos naturales y ambiente tranquilo. Ideal para desayunos y brunchs. Pet-friendly con patio interior.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0365, -12.0923],  # San Isidro
            "address": "Av. Paz Soldán 290, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["café", "vegano", "vegetariano", "saludable", "pet-friendly", "brunch", "patio"]
    },
    {
        "id": "place_lima_011",
        "image_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e",
        "title": "Parque El Olivar",
        "description": "Parque urbano histórico con olivos centenarios y senderos para correr. Perfecto para trotar, hacer ejercicio al aire libre o caminar. Ambiente muy tranquilo con pistas delimitadas para running en San Isidro.",
        "category": "Deportes",
        "location": {
            "coordinates": [-77.0380, -12.0950],  # San Isidro - Centro
            "address": "Av. Nicolás de Ribera, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["parque", "running", "correr", "trotar", "ejercicio", "naturaleza", "senderos", "deportes"]
    },
    {
        "id": "place_lima_012",
        "image_url": "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8",
        "title": "Costa Verde Running Track",
        "description": "Pista profesional de running con vista al mar en la Costa Verde. Superficie especializada para entrenamiento. Ideal para corredores de todos los niveles, cerca de San Isidro y Miraflores.",
        "category": "Deportes",
        "location": {
            "coordinates": [-77.0450, -12.1100],  # Entre San Isidro y Miraflores
            "address": "Circuito de Playas Costa Verde, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["pista", "running", "correr", "entrenamiento", "atletismo", "costa verde", "deportes", "profesional"]
    },
    {
        "id": "place_lima_013",
        "image_url": "https://images.unsplash.com/photo-1483721310020-03333e577078",
        "title": "Bosque El Olivar Running Circuit",
        "description": "Circuito de 3km para correr dentro del Bosque El Olivar. Senderos señalizados, ambiente natural y sombra de árboles. Muy popular entre runners de San Isidro. Horario: 6am-8pm.",
        "category": "Deportes",
        "location": {
            "coordinates": [-77.0360, -12.0940],  # San Isidro - Bosque
            "address": "Ingreso por Av. Arequipa, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["circuito", "running", "correr", "bosque", "naturaleza", "3km", "senderos", "deportes", "ambiente natural"]
    },
    {
        "id": "place_lima_014",
        "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        "title": "Café Tostado",
        "description": "Café de especialidad en Miraflores con opciones de brunch y almuerzo saludable. Ambiente moderno y acogedor. Muy bueno para trabajar con laptop.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0320, -12.1200],  # Miraflores
            "address": "Av. Conquistadores 995, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["café", "brunch", "saludable", "trabajo remoto", "moderno", "laptop", "wifi"]
    },
    {
        "id": "place_lima_015",
        "image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0",
        "title": "Maido",
        "description": "Restaurante nikkei de alta cocina, entre los mejores de Latinoamérica. Fusión peruano-japonesa excepcional. Requiere reserva con anticipación.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0350, -12.1150],  # Miraflores
            "address": "Calle San Martín 399, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["restaurante", "nikkei", "alta cocina", "fusión", "japonés", "reserva", "premiado"]
    },
    {
        "id": "place_lima_016",
        "image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0",
        "title": "Astrid y Gastón Casa Moreyra",
        "description": "Emblemático restaurante de Gastón Acurio en casona colonial. Cocina peruana contemporánea de autor. Experiencia gastronómica completa.",
        "category": "Gastronomía",
        "location": {
            "coordinates": [-77.0380, -12.0900],  # San Isidro
            "address": "Av. Paz Soldán 290, San Isidro",
            "neighborhood": "San Isidro"
        },
        "tags": ["restaurante", "peruano", "gastón acurio", "autor", "casona", "contemporáneo", "experiencia"]
    },
    {
        "id": "place_lima_017",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Museo de Arte de Lima (MALI)",
        "description": "Museo de arte con colecciones desde precolombino hasta contemporáneo. Exposiciones temporales y permanentes. Cafetería con jardín interior.",
        "category": "Cultura",
        "location": {
            "coordinates": [-77.0350, -12.0750],  # Cercado de Lima
            "address": "Paseo Colón 125, Cercado de Lima",
            "neighborhood": "Cercado de Lima"
        },
        "tags": ["museo", "arte", "historia", "exposiciones", "precolombino", "contemporáneo", "cafetería"]
    },
    {
        "id": "place_lima_018",
        "image_url": "https://images.unsplash.com/photo-1567696911980-2eed69a46042",
        "title": "Centro Histórico de Lima",
        "description": "Patrimonio de la Humanidad con Plaza de Armas, Catedral y Palacio de Gobierno. Arquitectura colonial impresionante. Tours guiados disponibles.",
        "category": "Cultura",
        "location": {
            "coordinates": [-77.0282, -12.0464],  # Cercado de Lima
            "address": "Plaza Mayor, Cercado de Lima",
            "neighborhood": "Cercado de Lima"
        },
        "tags": ["centro histórico", "patrimonio", "colonial", "catedral", "plaza mayor", "tours", "arquitectura"]
    },
    {
        "id": "place_lima_019",
        "image_url": "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8",
        "title": "Club Terrazas de Miraflores",
        "description": "Club deportivo en acantilado con gimnasio, piscinas y canchas. Vista al océano. Clases grupales y entrenamiento personal disponible.",
        "category": "Deportes",
        "location": {
            "coordinates": [-77.0420, -12.1350],  # Miraflores
            "address": "Malecón Cisneros, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["club", "gimnasio", "piscina", "canchas", "vista al mar", "clases", "entrenamiento"]
    },
    {
        "id": "place_lima_020",
        "image_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e",
        "title": "Parque Kennedy",
        "description": "Parque central de Miraflores con artesanías y gatos. Punto de encuentro popular rodeado de cafés y restaurantes. Ambiente seguro y familiar.",
        "category": "Entretenimiento",
        "location": {
            "coordinates": [-77.0300, -12.1200],  # Miraflores
            "address": "Av. Oscar R. Benavides, Miraflores",
            "neighborhood": "Miraflores"
        },
        "tags": ["parque", "artesanías", "gatos", "familiar", "céntrico", "encuentro", "seguro"]
    },
    {
        "id": "place_lima_021",
        "image_url": "https://images.unsplash.com/photo-1566417713940-fe7c737a9ef2",
        "title": "Puente de los Suspiros",
        "description": "Icónico puente de madera en Barranco. Mirador romántico con vistas a la Bajada de Baños. Tradicional lugar para pedir deseos.",
        "category": "Cultura",
        "location": {
            "coordinates": [-77.0225, -12.1478],  # Barranco
            "address": "Jr. Batallón Ayacucho, Barranco",
            "neighborhood": "Barranco"
        },
        "tags": ["puente", "histórico", "romántico", "mirador", "turístico", "tradición", "barranco"]
    },
    {
        "id": "place_lima_022",
        "image_url": "https://images.unsplash.com/photo-1533777324565-a040eb52facd",
        "title": "Jockey Plaza",
        "description": "Centro comercial premium en Surco. Tiendas de marca, cines, restaurantes y supermercado. Amplio estacionamiento y zona gourmet.",
        "category": "Compras",
        "location": {
            "coordinates": [-77.0084, -12.1000],  # Surco
            "address": "Av. Javier Prado Este 4200, Surco",
            "neighborhood": "Surco"
        },
        "tags": ["mall", "shopping", "premium", "cines", "restaurantes", "estacionamiento", "gourmet"]
    }
]


async def seed_lima_places():
    """Seed Lima places to MongoDB and Pinecone"""
    
    print("🌱 Starting Lima Places seed...")
    
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
    
        # Delete existing Lima places
        print("🗑️  Clearing existing Lima places...")
        lima_ids = [place["id"] for place in LIMA_PLACES]
        await posts_collection.delete_many({"id": {"$in": lima_ids}})
    
        # Insert places
        print(f"📝 Inserting {len(LIMA_PLACES)} Lima places...")
        
        for place_data in LIMA_PLACES:
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
            print(f"  ✅ {post.title}")
        
        # Create geospatial index
        print("📍 Creating geospatial index...")
        await posts_collection.create_index([("location.coordinates", "2dsphere")])
        
        print(f"\n✅ Seed completed! {len(LIMA_PLACES)} Lima places added")
        
        # Show summary
        categories = {}
        for place in LIMA_PLACES:
            cat = place["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\nPlaces by category:")
        for cat, count in categories.items():
            print(f"  - {cat}: {count}")
        
        print("\n🎉 Ready to test POC2 with Lima!")
        
    finally:
        # Close connections
        await MongoDB.disconnect()
        print("👋 Disconnected from MongoDB")


if __name__ == "__main__":
    asyncio.run(seed_lima_places())

