from sqlalchemy.orm import Session
from app.models.skill import Skill, SkillInput
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class SkillRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, skill_input: SkillInput) -> Skill:
        skill = Skill(**skill_input.model_dump())
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def get_by_id(self, skill_id: UUID) -> Optional[Skill]:
        return self.db.query(Skill).filter(Skill.id == skill_id).first()

    def get_by_name(self, name: str) -> Optional[Skill]:
        return self.db.query(Skill).filter(Skill.name == name).first()

    def get_all(self, active_only: bool = False, limit: int = 100) -> List[Skill]:
        query = self.db.query(Skill)
        if active_only:
            query = query.filter(Skill.active == True)
        return query.limit(limit).all()

    def update(self, skill_id: UUID, skill_input: SkillInput) -> Optional[Skill]:
        skill = self.get_by_id(skill_id)
        if not skill:
            return None
        
        for key, value in skill_input.model_dump().items():
            setattr(skill, key, value)
        
        skill.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def delete(self, skill_id: UUID) -> bool:
        skill = self.get_by_id(skill_id)
        if not skill:
            return False
        
        self.db.delete(skill)
        self.db.commit()
        return True

    def activate(self, skill_id: UUID) -> Optional[Skill]:
        skill = self.get_by_id(skill_id)
        if not skill:
            return None
        
        skill.active = True
        skill.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def deactivate(self, skill_id: UUID) -> Optional[Skill]:
        skill = self.get_by_id(skill_id)
        if not skill:
            return None
        
        skill.active = False
        skill.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(skill)
        return skill


def get_skill_repository(db: Session) -> SkillRepository:
    return SkillRepository(db)