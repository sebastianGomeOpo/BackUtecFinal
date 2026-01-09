"""
Escalation repository implementation using SQLAlchemy
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from ..database.models import EscalationModel
import uuid


class SQLAlchemyEscalationRepository:
    """SQLAlchemy implementation of escalation repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, escalation_data: dict) -> dict:
        """Create a new escalation"""
        escalation_id = str(uuid.uuid4())
        escalation_model = EscalationModel(
            id=escalation_id,
            conversation_id=escalation_data.get("conversation_id"),
            message=escalation_data.get("message"),
            reason=escalation_data.get("reason"),
            status=escalation_data.get("status", "pending"),
            assigned_to=escalation_data.get("assigned_to"),
        )
        self.session.add(escalation_model)
        await self.session.commit()
        return self._model_to_dict(escalation_model)

    async def get_by_id(self, escalation_id: str) -> Optional[dict]:
        """Get escalation by ID"""
        stmt = select(EscalationModel).where(EscalationModel.id == escalation_id)
        result = await self.session.execute(stmt)
        escalation_model = result.scalar_one_or_none()

        if escalation_model:
            return self._model_to_dict(escalation_model)
        return None

    async def get_by_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get escalation for a conversation (should be only one per conversation)"""
        stmt = select(EscalationModel).where(
            EscalationModel.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        escalation_model = result.scalar_one_or_none()

        if escalation_model:
            return self._model_to_dict(escalation_model)
        return None

    async def update_status(self, escalation_id: str, status: str) -> bool:
        """Update escalation status"""
        stmt = update(EscalationModel).where(
            EscalationModel.id == escalation_id
        ).values(status=status)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def resolve(
        self,
        escalation_id: str,
        resolution_notes: str
    ) -> bool:
        """Mark escalation as resolved"""
        stmt = update(EscalationModel).where(
            EscalationModel.id == escalation_id
        ).values(
            status="resolved",
            resolved_at=datetime.utcnow(),
            resolution_notes=resolution_notes
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_pending(self, limit: int = 50) -> List[dict]:
        """Get pending escalations"""
        stmt = select(EscalationModel).where(
            EscalationModel.status == "pending"
        ).limit(limit)

        result = await self.session.execute(stmt)
        escalation_models = result.scalars().all()

        return [self._model_to_dict(model) for model in escalation_models]

    async def get_by_status(self, status: str, limit: int = 50) -> List[dict]:
        """Get escalations by status"""
        stmt = select(EscalationModel).where(
            EscalationModel.status == status
        ).limit(limit)

        result = await self.session.execute(stmt)
        escalation_models = result.scalars().all()

        return [self._model_to_dict(model) for model in escalation_models]

    async def assign_to_agent(self, escalation_id: str, agent_id: str) -> bool:
        """Assign escalation to a human agent"""
        stmt = update(EscalationModel).where(
            EscalationModel.id == escalation_id
        ).values(
            assigned_to=agent_id,
            status="in_progress"
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    @staticmethod
    def _model_to_dict(model: EscalationModel) -> dict:
        """Convert SQLAlchemy model to dictionary"""
        return {
            "id": model.id,
            "conversation_id": model.conversation_id,
            "message": model.message,
            "reason": model.reason,
            "status": model.status,
            "assigned_to": model.assigned_to,
            "created_at": model.created_at,
            "resolved_at": model.resolved_at,
            "resolution_notes": model.resolution_notes,
        }
