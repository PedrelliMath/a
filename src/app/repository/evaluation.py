from sqlalchemy.orm import Session
from app.models.evaluation import Evaluation, EvaluationInput, EvaluationOutput
from uuid import UUID
from datetime import datetime
from typing import Optional
import json

class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, session, iterations) -> Evaluation:        
        evaluation = Evaluation(
            session_id=session.id,
            user_id=str(session.user_id),  
            skill_id=session.skill_id,
            iterations=iterations
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def get_all(self) -> Optional[list[Evaluation]]:
        return self.db.query(Evaluation).all()

    def get_by_id(self, evaluation_id: UUID) -> Optional[Evaluation]:
        return self.db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    def get_by_session_id(self, session_id: UUID) -> Optional[Evaluation]:
        return self.db.query(Evaluation).filter(Evaluation.session_id == session_id).first()
    
    def get_by_skill_id(self, skill_id: UUID, limit: int) -> Optional[Evaluation]:
        return self.db.query(Evaluation).filter(Evaluation.skill_id == skill_id).limit(limit).all()

    def update_iterations(self, evaluation_id: UUID, iterations: dict) -> Optional[Evaluation]:
        evaluation = self.get_by_id(evaluation_id)
        if not evaluation:
            return None
        
        evaluation.iterations = iterations
        evaluation.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def delete(self, evaluation_id: UUID) -> bool:
        evaluation = self.get_by_id(evaluation_id)
        if not evaluation:
            return False
        
        self.db.delete(evaluation)
        self.db.commit()
        return True


def get_evaluation_repository(db: Session) -> EvaluationRepository:
    return EvaluationRepository(db)