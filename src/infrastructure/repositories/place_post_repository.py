"""
Place Post repository implementation with local geospatial emulation
Replaces MongoDB 2dsphere queries with in-memory distance calculations
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ...domain.entities import PlacePost
from ...domain.repositories import IPlacePostRepository
from ..database.models import PlacePostModel
from geopy.distance import geodesic


class SQLAlchemyPlacePostRepository(IPlacePostRepository):
    """SQLAlchemy implementation of place post repository with local geospatial support"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, post: PlacePost) -> PlacePost:
        """Create a new place post"""
        post_model = self._entity_to_model(post)
        self.session.add(post_model)
        await self.session.commit()
        return post

    async def get_by_id(self, post_id: str) -> Optional[PlacePost]:
        """Get post by ID"""
        stmt = select(PlacePostModel).where(PlacePostModel.id == post_id)
        result = await self.session.execute(stmt)
        post_model = result.scalar_one_or_none()

        if post_model:
            return self._model_to_entity(post_model)
        return None

    async def get_all(self, limit: int = 50) -> List[PlacePost]:
        """Get all posts, ordered by most recent"""
        stmt = select(PlacePostModel).order_by(desc(PlacePostModel.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        post_models = result.scalars().all()

        return [self._model_to_entity(model) for model in post_models]

    async def delete(self, post_id: str) -> bool:
        """Delete a post"""
        post_model = await self.get_by_id(post_id)
        if post_model:
            stmt = select(PlacePostModel).where(PlacePostModel.id == post_id)
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                await self.session.delete(model)
                await self.session.commit()
                return True
        return False

    async def get_nearby(
        self,
        longitude: float,
        latitude: float,
        max_distance_km: float = 10.0,
        limit: int = 20
    ) -> List[PlacePost]:
        """
        Get posts near a location using in-memory distance calculation

        SQLite doesn't have native geospatial support, so we:
        1. Fetch all posts
        2. Calculate distances in-memory
        3. Filter and sort by distance

        This approach is simple but acceptable for datasets <10k posts.
        For larger datasets, consider PostGIS or a separate geospatial service.

        Args:
            longitude: User's longitude
            latitude: User's latitude
            max_distance_km: Maximum distance in kilometers
            limit: Maximum number of results

        Returns:
            List of nearby posts, sorted by distance
        """
        # Get all posts
        stmt = select(PlacePostModel)
        result = await self.session.execute(stmt)
        all_posts = result.scalars().all()

        # Calculate distances
        nearby_posts = []
        user_location = (latitude, longitude)

        for post_model in all_posts:
            post_location = (post_model.latitude, post_model.longitude)
            distance_km = self.calculate_distance(
                longitude, latitude,
                post_model.longitude, post_model.latitude
            )

            if distance_km <= max_distance_km:
                nearby_posts.append((post_model, distance_km))

        # Sort by distance and limit results
        nearby_posts.sort(key=lambda x: x[1])
        return [self._model_to_entity(model) for model, _ in nearby_posts[:limit]]

    @staticmethod
    def calculate_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calculate distance between two points using geodesic (Vincenty formula)

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

    # Helper methods
    @staticmethod
    def _model_to_entity(model: PlacePostModel) -> PlacePost:
        """Convert SQLAlchemy model to domain entity"""
        # Reconstruct the location object from lat/lon
        from ...domain.entities import Location

        location = Location(
            type="Point",
            coordinates=[model.longitude, model.latitude],
            address=model.address,
            neighborhood=model.neighborhood
        )

        return PlacePost(
            id=model.id,
            image_url=model.image_url,
            title=model.title,
            description=model.description,
            category=model.category,
            location=location,
            sponsor=model.sponsor,
            tags=model.tags or [],
            created_at=model.created_at,
            metadata=model.metadata or {},
        )

    @staticmethod
    def _entity_to_model(entity: PlacePost) -> PlacePostModel:
        """Convert domain entity to SQLAlchemy model"""
        return PlacePostModel(
            id=entity.id,
            image_url=entity.image_url,
            title=entity.title,
            description=entity.description,
            category=entity.category,
            latitude=entity.location.coordinates[1],  # [lon, lat] -> lat
            longitude=entity.location.coordinates[0],  # [lon, lat] -> lon
            address=entity.location.address,
            neighborhood=entity.location.neighborhood,
            sponsor=entity.sponsor,
            tags=entity.tags,
            metadata=entity.metadata,
        )
