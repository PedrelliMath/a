from sqlalchemy import update, func, text
from sqlalchemy.orm import Session as DBSession
from app.models.session import Session, SessionInput, SessionMessageInput
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional

class SessionRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, session_input: SessionInput) -> Session:
        session = Session(skill_id=session_input.skill_id, messages=[])
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_id(self, session_id: UUID) -> Optional[Session]:
        return self.db.query(Session).filter(Session.id == session_id).first()

    def get_all(self, limit: int = 100) -> List[Session]:
        return self.db.query(Session).order_by(Session.created_at.desc()).limit(limit).all()

    def get_by_skill_id(self, skill_id: UUID, limit: int = 100) -> List[Session]:
        return (
            self.db.query(Session)
            .filter(Session.skill_id == skill_id)
            .order_by(Session.created_at.desc())
            .limit(limit)
            .all()
        )

    def add_message(self, session: Session, user_type: str, message_input: SessionMessageInput, params: dict | None = None):

        message = {
            "id": str(uuid4()),
            "text": message_input.text,
            "user_type": user_type,
            "params": params or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        current_messages = session.messages if session.messages else []
        updated_messages = current_messages + [message] 
        session.messages = updated_messages
        
        session.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(session)
        return message

    def delete(self, session_id: UUID) -> bool:
        session = self.get_by_id(session_id)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True


def get_session_repository(db: DBSession) -> SessionRepository:
    return SessionRepository(db)