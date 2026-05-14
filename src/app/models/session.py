from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.db import Base
from uuid import uuid4, UUID
from datetime import datetime
from typing import List

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .skill import Skill
    from .evaluation import Evaluation


class SessionMessageInput(BaseModel):
    """Schema de entrada para mensagem"""
    text: str

class SessionMessageOutput(BaseModel):
    """Schema de saída para mensagem"""
    id: UUID
    text: str
    user_type: str
    created_at: datetime
    params: dict

class SessionInput(BaseModel):
    """Schema de entrada para criar sessão"""
    skill_id: UUID

class SessionOutput(BaseModel):
    """Schema de saída para sessão"""
    id: UUID
    skill_id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime


class Session(Base):
    """Modelo SQLAlchemy para Sessions"""
    __tablename__ = 'sessions'

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        unique=True, 
        nullable=False,
        default=uuid4
    )

    skill_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("skills.id"),
        nullable=False
    )

    user_id: Mapped[str] = mapped_column(
        String(36), 
        nullable=True,
        index=True
    )

    messages: Mapped[list] = mapped_column(
        JSONB, 
        server_default=text("'[]'::jsonb"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    skill: Mapped['Skill'] = relationship(back_populates="sessions")

    evaluation: Mapped['Evaluation'] = relationship(uselist=False, back_populates="session")

    def to_dict(self, include_messages: bool = False) -> dict:
        session_dict =  {
            "id":str(self.id),
            "skill_id":str(self.skill_id),
            "user_id":self.user_id,
            "created_at":self.created_at,
            "updated_at":self.updated_at
        }

        if include_messages:
            session_dict.update({
                "messages":self.messages
            })
        
        return session_dict