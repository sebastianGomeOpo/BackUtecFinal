"""
Customer repository implementation using SQLAlchemy
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...domain.entities import Customer
from ...domain.repositories import ICustomerRepository
from ..database.models import CustomerModel


class SQLAlchemyCustomerRepository(ICustomerRepository):
    """SQLAlchemy implementation of customer repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, customer: Customer) -> Customer:
        """Create a new customer"""
        customer_model = self._entity_to_model(customer)
        self.session.add(customer_model)
        await self.session.commit()
        return customer

    async def get_by_id(self, customer_id: str) -> Optional[Customer]:
        """Get customer by ID"""
        stmt = select(CustomerModel).where(CustomerModel.id == customer_id)
        result = await self.session.execute(stmt)
        customer_model = result.scalar_one_or_none()

        if customer_model:
            return self._model_to_entity(customer_model)
        return None

    async def update(self, customer: Customer) -> Customer:
        """Update existing customer"""
        stmt = select(CustomerModel).where(CustomerModel.id == customer.id)
        result = await self.session.execute(stmt)
        customer_model = result.scalar_one_or_none()

        if not customer_model:
            raise ValueError(f"Customer {customer.id} not found")

        # Update fields
        for field, value in customer.model_dump().items():
            setattr(customer_model, field, value)

        self.session.add(customer_model)
        await self.session.commit()
        return customer

    async def find_by_email(self, email: str) -> Optional[Customer]:
        """Find customer by email"""
        stmt = select(CustomerModel).where(CustomerModel.email == email)
        result = await self.session.execute(stmt)
        customer_model = result.scalar_one_or_none()

        if customer_model:
            return self._model_to_entity(customer_model)
        return None

    # Helper methods
    @staticmethod
    def _model_to_entity(model: CustomerModel) -> Customer:
        """Convert SQLAlchemy model to domain entity"""
        return Customer(
            id=model.id,
            name=model.name,
            email=model.email,
            phone=model.phone,
            location=model.location,
            preferences=model.preferences or {},
            purchase_history=model.purchase_history or [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _entity_to_model(entity: Customer) -> CustomerModel:
        """Convert domain entity to SQLAlchemy model"""
        return CustomerModel(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            phone=entity.phone,
            location=entity.location,
            preferences=entity.preferences,
            purchase_history=entity.purchase_history,
        )
