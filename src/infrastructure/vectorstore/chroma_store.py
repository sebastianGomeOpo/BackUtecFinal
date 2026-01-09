"""
ChromaDB Vector Store Wrapper
Replaces Pinecone with local embedding storage for semantic search
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from pathlib import Path
import httpx
import logging

logger = logging.getLogger(__name__)


class ChromaStore:
    """
    Wrapper for ChromaDB vector store
    Handles embedding generation and semantic search for products
    """

    _client: Optional[chromadb.Client] = None
    _products_collection = None
    _places_collection = None
    _persist_dir: str = "./data/chroma_db"

    @classmethod
    async def initialize(cls, persist_dir: str = "./data/chroma_db"):
        """Initialize ChromaDB with persistent storage"""
        cls._persist_dir = persist_dir

        try:
            # Ensure persist directory exists
            Path(persist_dir).mkdir(parents=True, exist_ok=True)

            # Create ChromaDB client with persistent storage
            cls._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True,
                )
            )

            # Get or create collections
            cls._products_collection = cls._client.get_or_create_collection(
                name="products",
                metadata={"hnsw:space": "cosine"},  # cosine similarity
            )

            cls._places_collection = cls._client.get_or_create_collection(
                name="places",
                metadata={"hnsw:space": "cosine"},
            )

            logger.info(f"✅ ChromaDB initialized at {persist_dir}")

        except Exception as e:
            logger.error(f"❌ ChromaDB initialization failed: {e}")
            raise

    @classmethod
    async def upsert_product(
        cls,
        product_id: str,
        name: str,
        description: str,
        category: str,
        sku: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Index a product in ChromaDB

        Args:
            product_id: Product ID
            name: Product name
            description: Product description
            category: Product category
            sku: Product SKU
            metadata: Additional metadata (name, category, SKU)

        Returns:
            Success flag
        """
        if not cls._products_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            # Combine text for embedding
            combined_text = f"{name} {description} {category}"
            if sku:
                combined_text += f" {sku}"

            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                "name": name,
                "category": category,
                "sku": sku or "",
            })

            # Upsert to ChromaDB (auto-generates embedding)
            cls._products_collection.upsert(
                ids=[product_id],
                documents=[combined_text],
                metadatas=[doc_metadata],
            )

            logger.debug(f"Indexed product {product_id}: {name}")
            return True

        except Exception as e:
            logger.error(f"Error upserting product {product_id}: {e}")
            return False

    @classmethod
    async def search_products(
        cls,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search products using semantic similarity

        Args:
            query: Search query (natural language)
            top_k: Number of results to return
            filters: Optional metadata filters (not yet implemented)

        Returns:
            List of matching products with scores
            Format: [{"id": str, "distance": float, "metadata": dict}, ...]
        """
        if not cls._products_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            # Query ChromaDB
            results = cls._products_collection.query(
                query_texts=[query],
                n_results=top_k,
            )

            # Format results
            products = []
            if results["ids"] and len(results["ids"]) > 0:
                for idx, product_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][idx] if results["distances"] else 0
                    metadata = results["metadatas"][0][idx] if results["metadatas"] else {}

                    products.append({
                        "id": product_id,
                        "distance": distance,  # Lower is more similar (cosine distance)
                        "metadata": metadata,
                    })

            logger.debug(f"Searched products for '{query}': found {len(products)} results")
            return products

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    @classmethod
    async def delete_product(cls, product_id: str) -> bool:
        """Delete a product from the vector store"""
        if not cls._products_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            cls._products_collection.delete(ids=[product_id])
            logger.debug(f"Deleted product {product_id} from vector store")
            return True
        except Exception as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return False

    # ============================================================================
    # Places Vector Store Methods
    # ============================================================================

    @classmethod
    async def upsert_place(
        cls,
        place_id: str,
        title: str,
        description: str,
        category: str,
        address: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Index a place in ChromaDB

        Args:
            place_id: Place ID
            title: Place title
            description: Place description
            category: Place category
            address: Place address
            metadata: Additional metadata

        Returns:
            Success flag
        """
        if not cls._places_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            # Combine text for embedding
            combined_text = f"{title} {description} {category}"
            if address:
                combined_text += f" {address}"

            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                "title": title,
                "category": category,
                "address": address or "",
            })

            # Upsert to ChromaDB
            cls._places_collection.upsert(
                ids=[place_id],
                documents=[combined_text],
                metadatas=[doc_metadata],
            )

            logger.debug(f"Indexed place {place_id}: {title}")
            return True

        except Exception as e:
            logger.error(f"Error upserting place {place_id}: {e}")
            return False

    @classmethod
    async def search_places(
        cls,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search places using semantic similarity

        Args:
            query: Search query (natural language)
            top_k: Number of results to return
            filters: Optional metadata filters (not yet implemented)

        Returns:
            List of matching places with scores
        """
        if not cls._places_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            # Query ChromaDB
            results = cls._places_collection.query(
                query_texts=[query],
                n_results=top_k,
            )

            # Format results
            places = []
            if results["ids"] and len(results["ids"]) > 0:
                for idx, place_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][idx] if results["distances"] else 0
                    metadata = results["metadatas"][0][idx] if results["metadatas"] else {}

                    places.append({
                        "id": place_id,
                        "distance": distance,
                        "metadata": metadata,
                    })

            logger.debug(f"Searched places for '{query}': found {len(places)} results")
            return places

        except Exception as e:
            logger.error(f"Error searching places: {e}")
            return []

    @classmethod
    async def delete_place(cls, place_id: str) -> bool:
        """Delete a place from the vector store"""
        if not cls._places_collection:
            raise RuntimeError("ChromaDB not initialized. Call initialize() first.")

        try:
            cls._places_collection.delete(ids=[place_id])
            logger.debug(f"Deleted place {place_id} from vector store")
            return True
        except Exception as e:
            logger.error(f"Error deleting place {place_id}: {e}")
            return False

    @classmethod
    async def get_stats(cls) -> Dict[str, Any]:
        """Get ChromaDB statistics"""
        if not cls._client:
            return {"status": "not_initialized"}

        try:
            product_count = cls._products_collection.count() if cls._products_collection else 0
            places_count = cls._places_collection.count() if cls._places_collection else 0

            return {
                "status": "initialized",
                "persist_dir": cls._persist_dir,
                "products_indexed": product_count,
                "places_indexed": places_count,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error", "message": str(e)}

    @classmethod
    async def reset(cls):
        """Reset all collections (for testing)"""
        if cls._client:
            try:
                cls._client.reset()
                logger.info("ChromaDB reset")
            except Exception as e:
                logger.error(f"Error resetting ChromaDB: {e}")
