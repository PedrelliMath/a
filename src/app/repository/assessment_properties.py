from sqlalchemy.orm import Session
from app.models.assessment_properties import AssessmentProperties
from datetime import datetime
from typing import Optional


class AssessmentPropertiesRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self) -> Optional[AssessmentProperties]:
        return self.db.query(AssessmentProperties).first()

    def create(self, duration_minutes: int) -> AssessmentProperties:
        properties = AssessmentProperties(
            duration_minutes=duration_minutes
        )
        self.db.add(properties)
        self.db.commit()
        self.db.refresh(properties)
        return properties

    def get_or_create(self, default_duration_minutes: int = 30) -> AssessmentProperties:
        properties = self.get()
        if not properties:
            properties = self.create(default_duration_minutes)
        return properties

    def update_duration(self, duration_minutes: int) -> AssessmentProperties:
        properties = self.get_or_create()
        properties.duration_minutes = duration_minutes
        properties.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(properties)
        return properties


def get_assessment_properties_repository(db: Session) -> AssessmentPropertiesRepository:
    return AssessmentPropertiesRepository(db)