"""
Repository interfaces - Domain contracts for data access
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .entities import Customer, Product, Quote, PlacePost, UserLocation, PlaceRecommendation


class ICustomerRepository(ABC):
    """Interface for customer data access"""
    
    @abstractmethod
    async def create(self, customer: Customer) -> Customer:
        """Create a new customer"""
        pass
    
    @abstractmethod
    async def get_by_id(self, customer_id: str) -> Optional[Customer]:
        """Get customer by ID"""
        pass
    
    @abstractmethod
    async def update(self, customer: Customer) -> Customer:
        """Update existing customer"""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[Customer]:
        """Find customer by email"""
        pass


class IProductRepository(ABC):
    """Interface for product data access"""
    
    @abstractmethod
    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[Product]:
        """Search products"""
        pass
    
    @abstractmethod
    async def check_stock(self, product_id: str) -> int:
        """Check product stock"""
        pass
    
    @abstractmethod
    async def get_price(self, product_id: str) -> float:
        """Get product price"""
        pass
    
    @abstractmethod
    async def get_by_category(self, category: str, limit: int = 10) -> List[Product]:
        """Get products by category"""
        pass


class IQuoteRepository(ABC):
    """Interface for quote data access"""
    
    @abstractmethod
    async def create(self, quote: Quote) -> Quote:
        """Create a new quote"""
        pass
    
    @abstractmethod
    async def get_by_id(self, quote_id: str) -> Optional[Quote]:
        """Get quote by ID"""
        pass
    
    @abstractmethod
    async def update(self, quote: Quote) -> Quote:
        """Update existing quote"""
        pass
    
    @abstractmethod
    async def get_by_conversation(self, conversation_id: str) -> List[Quote]:
        """Get quotes for a conversation"""
        pass


class IVectorStoreRepository(ABC):
    """Interface for vector store (RAG) operations"""
    
    @abstractmethod
    async def search_products(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search products using semantic search"""
        pass
    
    @abstractmethod
    async def upsert_product(self, product: Product) -> None:
        """Add or update product in vector store"""
        pass
    
    @abstractmethod
    async def delete_product(self, product_id: str) -> None:
        """Delete product from vector store"""
        pass


# ============================================================================
# PLACES RECOMMENDER REPOSITORIES
# ============================================================================

class IPlacePostRepository(ABC):
    """Interface for place post data access"""
    
    @abstractmethod
    async def create(self, post: PlacePost) -> PlacePost:
        """Create a new place post"""
        pass
    
    @abstractmethod
    async def get_by_id(self, post_id: str) -> Optional[PlacePost]:
        """Get post by ID"""
        pass
    
    @abstractmethod
    async def get_all(self, limit: int = 50) -> List[PlacePost]:
        """Get all posts"""
        pass
    
    @abstractmethod
    async def delete(self, post_id: str) -> bool:
        """Delete a post"""
        pass
    
    @abstractmethod
    async def get_nearby(
        self, 
        longitude: float, 
        latitude: float, 
        max_distance_km: float = 10.0,
        limit: int = 20
    ) -> List[PlacePost]:
        """Get posts near a location (geospatial query)"""
        pass


class IPlacesVectorStoreRepository(ABC):
    """Interface for places vector store (RAG) operations"""
    
    @abstractmethod
    async def search_places(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search places using semantic search"""
        pass
    
    @abstractmethod
    async def upsert_place(self, post: PlacePost) -> None:
        """Add or update place in vector store"""
        pass
    
    @abstractmethod
    async def delete_place(self, post_id: str) -> None:
        """Delete place from vector store"""
        pass
