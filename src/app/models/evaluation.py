from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, String, text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.db import Base
from uuid import uuid4, UUID
from datetime import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session
    from .skill import Skill

iteration_example = [
    {
        "macro":"Autoconhecimento",
        "question":"Quais comportamentos você percebe que se repetem em situações de pressão?",
        "response":"Não sei",
        "expected_bloom_level":"Criar",
        "achieved_bloom_level":"Lembrar"
    }
]

class EvaluationInput(BaseModel):
    pass

class EvaluationOutput(BaseModel):
    id: UUID
    user_id: UUID
    skill_id: UUID
    session_id: UUID
    iterations: dict = Field(
        examples=[
            iteration_example,
            iteration_example
        ]
    )
    created_at: datetime
    updated_at: datetime

class Evaluation(Base):
    __tablename__ = 'evaluations'

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        unique=True, 
        nullable=False,
        default=uuid4
    )

    user_id: Mapped[str] = mapped_column(
        String(36), 
        nullable=True
    )

    skill_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("skills.id"),
        nullable=False
    )

    session_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("sessions.id"),
        nullable=False
    )

    iterations: Mapped[list] = mapped_column(
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

    session: Mapped['Session'] = relationship(uselist=False, back_populates="evaluation")

    skill: Mapped['Skill'] = relationship(back_populates="evaluations")

    def to_dict(self):
        return {
            "id":str(self.id),
            "session_id":str(self.session_id),
            "user_id":self.user_id,
            "skill_id":str(self.skill_id),
            "iterations":self.iterations
        }