from pydantic import BaseModel
from sqlalchemy import Integer, text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.db import Base
from uuid import uuid4, UUID
from datetime import datetime


class AssessmentPropertiesInput(BaseModel):
    """Schema de entrada para configuração do assessment"""
    duration_minutes: int


class AssessmentPropertiesOutput(BaseModel):
    """Schema de saída para configuração do assessment"""
    id: UUID
    duration_minutes: int
    created_at: datetime
    updated_at: datetime


class AssessmentProperties(Base):
    """Modelo SQLAlchemy para configurações globais do assessment (singleton)"""
    __tablename__ = 'assessment_properties'

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        unique=True,
        nullable=False,
        default=uuid4
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30")
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

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "duration_minutes": self.duration_minutes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }