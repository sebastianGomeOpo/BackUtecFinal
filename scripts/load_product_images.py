"""
Script para cargar imágenes de productos desde Unsplash y guardarlas en MongoDB
Las imágenes se suben a Cloudflare R2 y las URLs firmadas se guardan en MongoDB
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
import httpx

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "AgentN")

# Unsplash image URLs for different product categories
UNSPLASH_IMAGES = {
    "Muebles de Sala": [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=400",  # Sofá
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=400",  # Sofá moderno
        "https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?w=400",  # Sala
        "https://images.unsplash.com/photo-1567016432779-094069958ea5?w=400",  # Sofá gris
    ],
    "Muebles de Dormitorio": [
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=400",  # Cama
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=400",  # Dormitorio
        "https://images.unsplash.com/photo-1588046130717-0eb0c9a3ba15?w=400",  # Cama moderna
    ],
    "Iluminación": [
        "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400",  # Lámpara
        "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?w=400",  # Lámpara de pie
        "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=400",  # Lámpara moderna
    ],
    "Decoración": [
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=400",  # Decoración
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400",  # Espejo
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400",  # Alfombra
    ],
    "Cocina": [
        "https://images.unsplash.com/photo-1556909114-44e3e70034e2?w=400",  # Cocina
        "https://images.unsplash.com/photo-1584568694244-14fbdf83bd30?w=400",  # Utensilios
        "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?w=400",  # Ollas
    ],
    "Textiles": [
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=400",  # Textiles
        "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=400",  # Sábanas
    ],
    "default": [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=400",
    ]
}


async def get_image_for_category(category: str, index: int = 0) -> str:
    """Get an Unsplash image URL for a category"""
    images = UNSPLASH_IMAGES.get(category, UNSPLASH_IMAGES["default"])
    return images[index % len(images)]


async def upload_to_r2(image_url: str, object_key: str) -> dict:
    """Upload image from URL to Cloudflare R2"""
    try:
        # Import R2 service
        from src.infrastructure.services.cloudflare_r2 import get_r2_service
        r2 = get_r2_service()
        
        result = await r2.download_and_upload_image(
            source_url=image_url,
            object_key=object_key
        )
        return result
    except Exception as e:
        print(f"Error uploading to R2: {e}")
        return {"success": False, "error": str(e)}


async def update_products_with_images():
    """Update all products in MongoDB with images from Unsplash via R2"""
    print("\n" + "="*60)
    print("CARGANDO IMÁGENES DE PRODUCTOS")
    print("="*60)
    
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    
    # Get all products
    products = await db.products.find({}).to_list(length=None)
    print(f"📦 Total productos: {len(products)}")
    
    category_counters = {}
    updated_count = 0
    
    for product in products:
        product_id = product.get("id") or str(product.get("_id"))
        product_name = product.get("name", "Unknown")
        category = product.get("category", "default")
        
        # Check if product already has images
        existing_images = product.get("images", [])
        if existing_images and len(existing_images) > 0 and existing_images[0].startswith("http"):
            print(f"⏭️  {product_name} ya tiene imagen")
            continue
        
        # Get category counter
        if category not in category_counters:
            category_counters[category] = 0
        
        # Get Unsplash image URL
        unsplash_url = await get_image_for_category(category, category_counters[category])
        category_counters[category] += 1
        
        # Upload to R2
        object_key = f"products/{product_id}.jpg"
        print(f"📤 Subiendo imagen para: {product_name}")
        
        result = await upload_to_r2(unsplash_url, object_key)
        
        if result.get("success"):
            # Update product in MongoDB with the signed URL
            signed_url = result.get("signed_url")
            
            # Store both the object_key (permanent) and a placeholder for signed URL
            await db.products.update_one(
                {"_id": product["_id"]},
                {
                    "$set": {
                        "images": [object_key],  # Store object key, generate signed URL on demand
                        "image_key": object_key,
                        "updated_at": asyncio.get_event_loop().time()
                    }
                }
            )
            print(f"✅ {product_name} - Imagen guardada: {object_key}")
            updated_count += 1
        else:
            print(f"❌ Error con {product_name}: {result.get('error')}")
    
    client.close()
    print(f"\n📊 Total actualizados: {updated_count}/{len(products)}")


async def main():
    await update_products_with_images()


if __name__ == "__main__":
    asyncio.run(main())
