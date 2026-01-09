"""
Pinecone Store Compatibility Layer
This is a compatibility shim that forwards calls to ChromaDB.
Allows gradual migration without breaking existing code.
"""

from .chroma_store import ChromaStore
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PineconeStore:
    """
    Compatibility wrapper for Pinecone using ChromaDB backend.
    This allows existing code to work without changes while we migrate.
    """

    def __init__(self):
        """Initialize Pinecone Store (actually ChromaDB)"""
        if not ChromaStore._client:
            logger.warning("ChromaDB not initialized. Call ChromaStore.initialize() first.")

    async def search_products(
        self,
        query: str = None,
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for products - delegates to ChromaDB

        Args:
            query: Search query
            filter: Metadata filters (not used by ChromaDB yet)
            top_k: Number of results

        Returns:
            List of product results with IDs
        """
        if not query:
            return []

        try:
            results = await ChromaStore.search_products(query=query, top_k=top_k)
            # Convert ChromaDB format to expected Pinecone format
            return [{"id": r["id"], "metadata": r["metadata"], "score": 1 - r["distance"]} for r in results]
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    async def upsert_product(
        self,
        product_id: str,
        text: str = None,
        metadata: Dict[str, Any] = None,
        **kwargs
    ) -> bool:
        """
        Index a product in the vector store

        Args:
            product_id: Product ID
            text: Text to embed
            metadata: Metadata to store

        Returns:
            Success flag
        """
        if not text or not product_id:
            return False

        try:
            # Extract metadata fields
            name = metadata.get("name", "") if metadata else ""
            description = metadata.get("description", "") if metadata else ""
            category = metadata.get("category", "") if metadata else ""
            sku = metadata.get("sku", "") if metadata else None

            return await ChromaStore.upsert_product(
                product_id=product_id,
                name=name,
                description=description,
                category=category,
                sku=sku,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error upserting product {product_id}: {e}")
            return False

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product from the vector store"""
        try:
            return await ChromaStore.delete_product(product_id)
        except Exception as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return False

    # Places methods
    async def search_places(
        self,
        query: str = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search for places using ChromaDB"""
        if not query:
            return []

        try:
            results = await ChromaStore.search_places(query=query, top_k=top_k)
            return [{"id": r["id"], "metadata": r["metadata"], "score": 1 - r["distance"]} for r in results]
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            return []

    async def upsert_place(
        self,
        place_id: str,
        text: str = None,
        metadata: Dict[str, Any] = None,
        **kwargs
    ) -> bool:
        """Index a place in the vector store"""
        if not text or not place_id:
            return False

        try:
            # Extract metadata fields
            title = metadata.get("title", "") if metadata else ""
            description = metadata.get("description", "") if metadata else ""
            category = metadata.get("category", "") if metadata else ""
            address = metadata.get("address", "") if metadata else None

            return await ChromaStore.upsert_place(
                place_id=place_id,
                title=title,
                description=description,
                category=category,
                address=address,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error upserting place {place_id}: {e}")
            return False

    async def delete_place(self, place_id: str) -> bool:
        """Delete a place from the vector store"""
        try:
            return await ChromaStore.delete_place(place_id)
        except Exception as e:
            logger.error(f"Error deleting place {place_id}: {e}")
            return False
