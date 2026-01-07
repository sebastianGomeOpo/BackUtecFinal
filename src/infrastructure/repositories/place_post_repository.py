"""
Place Post repository implementation with geospatial support
"""
from typing import List, Optional
from ...domain.entities import PlacePost
from ...domain.repositories import IPlacePostRepository
from ..database.mongodb import MongoDB
from geopy.distance import geodesic


class MongoPlacePostRepository(IPlacePostRepository):
    """MongoDB implementation of place post repository"""
    
    def __init__(self):
        self.collection = MongoDB.get_database()["place_posts"]
        # Ensure geospatial index exists
        self._ensure_geospatial_index()
    
    def _ensure_geospatial_index(self):
        """Create 2dsphere index for geospatial queries"""
        try:
            self.collection.create_index([("location.coordinates", "2dsphere")])
        except Exception as e:
            print(f"Index might already exist: {e}")
    
    async def create(self, post: PlacePost) -> PlacePost:
        """Create a new place post"""
        post_dict = post.dict()
        await self.collection.insert_one(post_dict)
        return post
    
    async def get_by_id(self, post_id: str) -> Optional[PlacePost]:
        """Get post by ID"""
        doc = await self.collection.find_one({"id": post_id})
        if doc:
            doc.pop('_id', None)
            return PlacePost(**doc)
        return None
    
    async def get_all(self, limit: int = 50) -> List[PlacePost]:
        """Get all posts, ordered by most recent"""
        cursor = self.collection.find().sort("created_at", -1).limit(limit)
        
        posts = []
        async for doc in cursor:
            doc.pop('_id', None)
            posts.append(PlacePost(**doc))
        return posts
    
    async def delete(self, post_id: str) -> bool:
        """Delete a post"""
        result = await self.collection.delete_one({"id": post_id})
        return result.deleted_count > 0
    
    async def get_nearby(
        self, 
        longitude: float, 
        latitude: float, 
        max_distance_km: float = 10.0,
        limit: int = 20
    ) -> List[PlacePost]:
        """
        Get posts near a location using MongoDB's geospatial queries
        
        Args:
            longitude: User's longitude
            latitude: User's latitude
            max_distance_km: Maximum distance in kilometers
            limit: Maximum number of results
        
        Returns:
            List of nearby posts
        """
        # MongoDB uses meters for distance
        max_distance_meters = max_distance_km * 1000
        
        cursor = self.collection.find({
            "location.coordinates": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude]
                    },
                    "$maxDistance": max_distance_meters
                }
            }
        }).limit(limit)
        
        posts = []
        async for doc in cursor:
            doc.pop('_id', None)
            posts.append(PlacePost(**doc))
        return posts
    
    @staticmethod
    def calculate_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calculate distance between two points using geopy's geodesic calculation
        
        Args:
            lon1: Longitude of first point
            lat1: Latitude of first point
            lon2: Longitude of second point
            lat2: Latitude of second point
        
        Returns:
            Distance in kilometers
        """
        # geopy uses (latitude, longitude) format
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        
        return geodesic(point1, point2).kilometers
