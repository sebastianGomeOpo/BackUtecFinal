"""
Domain entities - Core business objects
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Product(BaseModel):
    """Product entity"""
    id: str
    name: str
    description: str
    category: str
    price: float
    stock: int
    sku: str
    images: List[str] = []
    specifications: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}


class Customer(BaseModel):
    """Customer entity"""
    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    preferences: Dict[str, Any] = {}
    purchase_history: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QuoteItem(BaseModel):
    """Quote item entity"""
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float
    discount: float = 0.0


class Quote(BaseModel):
    """Quote entity"""
    id: str
    conversation_id: str
    customer_id: Optional[str] = None
    items: List[QuoteItem]
    subtotal: float
    discount: float = 0.0
    tax: float = 0.0
    total: float
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


# ============================================================================
# PLACES RECOMMENDER ENTITIES
# ============================================================================

class Location(BaseModel):
    """Geographic location"""
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]
    address: str
    neighborhood: Optional[str] = None
    

class PlacePost(BaseModel):
    """Instagram-style post for place recommendation"""
    id: str
    image_url: str
    title: str
    description: str
    category: str  # Gastronomía, Entretenimiento, Cultura, etc.
    location: Location
    sponsor: str = "Coca-Cola Andina"
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class UserLocation(BaseModel):
    """User's current location"""
    coordinates: List[float]  # [longitude, latitude]
    address: Optional[str] = None
    accuracy: Optional[float] = None  # meters


class PlaceRecommendation(BaseModel):
    """Place recommendation with distance info"""
    post: PlacePost
    distance_km: float
    distance_text: str  # "1.2 km de ti"
