"""
Product repository implementation
"""
from typing import List, Optional
from ...domain.entities import Product
from ...domain.repositories import IProductRepository
from ..database.mongodb import MongoDB


class MongoProductRepository(IProductRepository):
    """MongoDB implementation of product repository"""
    
    def __init__(self):
        self.collection = MongoDB.get_database()["products"]
    
    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        doc = await self.collection.find_one({"id": product_id})
        if doc:
            doc.pop('_id', None)
            return Product(**doc)
        return None
    
    async def search(self, query: str, limit: int = 10) -> List[Product]:
        """Search products by name or description"""
        cursor = self.collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}}
            ]
        }).limit(limit)
        
        products = []
        async for doc in cursor:
            doc.pop('_id', None)
            products.append(Product(**doc))
        return products
    
    async def check_stock(self, product_id: str) -> int:
        """Check product stock"""
        product = await self.get_by_id(product_id)
        return product.stock if product else 0
    
    async def get_price(self, product_id: str) -> float:
        """Get product price"""
        product = await self.get_by_id(product_id)
        return product.price if product else 0.0
    
    async def get_by_category(self, category: str, limit: int = 10) -> List[Product]:
        """Get products by category"""
        cursor = self.collection.find(
            {"category": {"$regex": category, "$options": "i"}}
        ).limit(limit)
        
        products = []
        async for doc in cursor:
            doc.pop('_id', None)
            products.append(Product(**doc))
        return products
    
    async def create(self, product: Product) -> Product:
        """Create a new product"""
        product_dict = product.model_dump(mode='json')
        await self.collection.insert_one(product_dict)
        return product
    
    async def update(self, product: Product) -> Product:
        """Update existing product"""
        product_dict = product.model_dump(mode='json')
        product_dict.pop('_id', None)
        
        await self.collection.update_one(
            {"id": product.id},
            {"$set": product_dict}
        )
        return product
    
    async def update_stock(self, product_id: str, quantity: int) -> None:
        """Update product stock"""
        await self.collection.update_one(
            {"id": product_id},
            {"$inc": {"stock": quantity}}
        )
    
    async def list_all(self, limit: int = 100) -> List[Product]:
        """List all products"""
        cursor = self.collection.find({}).limit(limit)
        
        products = []
        async for doc in cursor:
            doc.pop('_id', None)
            products.append(Product(**doc))
        return products
