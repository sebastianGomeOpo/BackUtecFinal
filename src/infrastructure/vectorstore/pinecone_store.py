"""
Pinecone vector store implementation for RAG
Native implementation - no LangChain
"""
from pinecone import Pinecone, ServerlessSpec
from typing import List, Optional, Dict, Any
import httpx
from ...config import settings
from ...domain.repositories import IVectorStoreRepository
from ...domain.entities import Product


class PineconeStore(IVectorStoreRepository):
    """Pinecone vector store for semantic product search"""
    
    _client: Optional[Pinecone] = None
    _index = None
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSION = 1536
    
    @classmethod
    async def initialize(cls):
        """Initialize Pinecone connection"""
        cls._client = Pinecone(api_key=settings.pinecone_api_key)
        
        # Create index if it doesn't exist
        index_name = settings.pinecone_index_name
        existing_indexes = cls._client.list_indexes()
        
        # Extract index names from IndexList object
        index_names = [idx['name'] for idx in existing_indexes]
        
        if index_name not in index_names:
            cls._client.create_index(
                name=index_name,
                dimension=cls.EMBEDDING_DIMENSION,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region=settings.pinecone_environment
                )
            )
            print(f"✅ Created Pinecone index: {index_name}")
        
        cls._index = cls._client.Index(index_name)
        print(f"✅ Connected to Pinecone index: {index_name}")
    
    @classmethod
    async def _get_embedding(cls, text: str) -> List[float]:
        """Get embedding for text using OpenAI API directly"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": text,
                    "model": cls.EMBEDDING_MODEL
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    
    @classmethod
    def get_index(cls):
        """Get Pinecone index instance"""
        if cls._index is None:
            raise RuntimeError("Pinecone not initialized. Call initialize() first.")
        return cls._index
    
    async def search_products(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search products using semantic search"""
        index = self.get_index()
        
        # Generate embedding for query
        query_embedding = await self._get_embedding(query)
        
        # Search in Pinecone
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filters
        )
        
        # Format results
        products = []
        for match in results.matches:
            product_data = {
                "id": match.id,
                "score": match.score,
                **match.metadata
            }
            products.append(product_data)
        
        return products
    
    async def upsert_product(self, product: Product) -> None:
        """Add or update product in vector store"""
        index = self.get_index()
        
        # Create text representation of product for embedding
        # Include all info for better search, but metadata will be minimal
        product_text = f"""
        {product.name}
        {product.description}
        Categoría: {product.category}
        SKU: {product.sku}
        """
        
        # Generate embedding
        embedding = await self._get_embedding(product_text)
        
        # Prepare metadata - ONLY display fields (Hybrid Approach)
        # Price and stock come from MongoDB when needed
        metadata = {
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "sku": product.sku,
            "images": product.images[:3] if product.images else [],  # Limit to 3 images
            # ❌ NO price - MongoDB is source of truth
            # ❌ NO stock - MongoDB is source of truth
        }
        
        # Upsert to Pinecone
        index.upsert(vectors=[{
            "id": product.id,
            "values": embedding,
            "metadata": metadata
        }])
    
    async def delete_product(self, product_id: str) -> None:
        """Delete product from vector store"""
        index = self.get_index()
        index.delete(ids=[product_id])
