"""
Product repository implementation using SQLAlchemy
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from ...domain.entities import Product
from ..database.models import ProductModel
from ..database.sqlite_db import Database


class SQLAlchemyProductRepository:
    """SQLAlchemy implementation of product repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        stmt = select(ProductModel).where(ProductModel.id == product_id)
        result = await self.session.execute(stmt)
        product_model = result.scalar_one_or_none()

        if product_model:
            return self._model_to_entity(product_model)
        return None

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU"""
        stmt = select(ProductModel).where(ProductModel.sku == sku)
        result = await self.session.execute(stmt)
        product_model = result.scalar_one_or_none()

        if product_model:
            return self._model_to_entity(product_model)
        return None

    async def search(self, query: str, limit: int = 10) -> List[Product]:
        """Search products by name, description, or category"""
        search_term = f"%{query}%"
        stmt = select(ProductModel).where(
            or_(
                ProductModel.name.ilike(search_term),
                ProductModel.description.ilike(search_term),
                ProductModel.category.ilike(search_term),
                ProductModel.sku.ilike(search_term),
            )
        ).limit(limit)

        result = await self.session.execute(stmt)
        product_models = result.scalars().all()
        return [self._model_to_entity(model) for model in product_models]

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
        search_term = f"%{category}%"
        stmt = select(ProductModel).where(
            ProductModel.category.ilike(search_term)
        ).limit(limit)

        result = await self.session.execute(stmt)
        product_models = result.scalars().all()
        return [self._model_to_entity(model) for model in product_models]

    async def get_by_ids(self, product_ids: List[str], limit: int = 100) -> List[Product]:
        """Get products by multiple IDs"""
        stmt = select(ProductModel).where(
            ProductModel.id.in_(product_ids)
        ).limit(limit)

        result = await self.session.execute(stmt)
        product_models = result.scalars().all()
        return [self._model_to_entity(model) for model in product_models]

    async def create(self, product: Product) -> Product:
        """Create a new product"""
        product_model = self._entity_to_model(product)
        self.session.add(product_model)
        await self.session.commit()
        return product

    async def update(self, product: Product) -> Product:
        """Update existing product"""
        stmt = select(ProductModel).where(ProductModel.id == product.id)
        result = await self.session.execute(stmt)
        product_model = result.scalar_one_or_none()

        if not product_model:
            raise ValueError(f"Product {product.id} not found")

        # Update fields
        for field, value in product.model_dump().items():
            setattr(product_model, field, value)

        self.session.add(product_model)
        await self.session.commit()
        return product

    async def update_stock(self, product_id: str, quantity: int) -> None:
        """Update product stock (atomic increment)"""
        stmt = update(ProductModel).where(
            ProductModel.id == product_id
        ).values(stock=ProductModel.stock + quantity)

        await self.session.execute(stmt)
        await self.session.commit()

    async def list_all(self, limit: int = 100) -> List[Product]:
        """List all products"""
        stmt = select(ProductModel).limit(limit)
        result = await self.session.execute(stmt)
        product_models = result.scalars().all()
        return [self._model_to_entity(model) for model in product_models]

    async def delete(self, product_id: str) -> bool:
        """Delete a product"""
        product = await self.get_by_id(product_id)
        if product:
            await self.session.delete(product)
            await self.session.commit()
            return True
        return False

    # Helper methods
    @staticmethod
    def _model_to_entity(model: ProductModel) -> Product:
        """Convert SQLAlchemy model to domain entity"""
        return Product(
            id=model.id,
            name=model.name,
            description=model.description,
            category=model.category,
            price=model.price,
            stock=model.stock,
            sku=model.sku,
            images=model.images or [],
            specifications=model.specifications or {},
            metadata=model.meta_data or {},
        )

    @staticmethod
    def _entity_to_model(entity: Product) -> ProductModel:
        """Convert domain entity to SQLAlchemy model"""
        return ProductModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            category=entity.category,
            price=entity.price,
            stock=entity.stock,
            sku=entity.sku,
            images=entity.images,
            specifications=entity.specifications,
            meta_data=entity.metadata,
        )


class MongoProductRepository:
    """
    MongoDB-compatible wrapper for SQLAlchemyProductRepository.
    Manages its own session internally for backward compatibility.
    """

    async def _get_repo(self) -> tuple[SQLAlchemyProductRepository, AsyncSession]:
        """Get a repository with its own session"""
        session_gen = Database.get_session()
        session = await anext(session_gen)
        return SQLAlchemyProductRepository(session), session

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_id(product_id)
        finally:
            await session.close()

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU"""
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_sku(sku)
        finally:
            await session.close()

    async def search(self, query: str, limit: int = 10) -> List[Product]:
        """Search products"""
        repo, session = await self._get_repo()
        try:
            return await repo.search(query, limit)
        finally:
            await session.close()

    async def check_stock(self, product_id: str) -> int:
        """Check product stock"""
        repo, session = await self._get_repo()
        try:
            return await repo.check_stock(product_id)
        finally:
            await session.close()

    async def get_price(self, product_id: str) -> float:
        """Get product price"""
        repo, session = await self._get_repo()
        try:
            return await repo.get_price(product_id)
        finally:
            await session.close()

    async def get_by_category(self, category: str, limit: int = 10) -> List[Product]:
        """Get products by category"""
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_category(category, limit)
        finally:
            await session.close()

    async def get_by_ids(self, product_ids: List[str], limit: int = 100) -> List[Product]:
        """Get products by multiple IDs"""
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_ids(product_ids, limit)
        finally:
            await session.close()

    async def list_all(self, limit: int = 100) -> List[Product]:
        """List all products"""
        repo, session = await self._get_repo()
        try:
            return await repo.list_all(limit)
        finally:
            await session.close()

    async def create(self, product: Product) -> Product:
        """Create a new product"""
        repo, session = await self._get_repo()
        try:
            return await repo.create(product)
        finally:
            await session.close()

    async def update(self, product: Product) -> Product:
        """Update existing product"""
        repo, session = await self._get_repo()
        try:
            return await repo.update(product)
        finally:
            await session.close()

    async def update_stock(self, product_id: str, quantity: int) -> None:
        """Update product stock"""
        repo, session = await self._get_repo()
        try:
            await repo.update_stock(product_id, quantity)
        finally:
            await session.close()

    async def delete(self, product_id: str) -> bool:
        """Delete a product"""
        repo, session = await self._get_repo()
        try:
            return await repo.delete(product_id)
        finally:
            await session.close()
