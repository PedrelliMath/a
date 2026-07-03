from fastapi import HTTPException, status
from app.models.session import Session, SessionInput, SessionOutput, SessionMessageInput, SessionMessageOutput
from app.models.current_user import CurrentUser
from app.repository.session import SessionRepository
from app.repository.skill import SkillRepository
from app.repository.assessment_properties import AssessmentPropertiesRepository
from uuid import UUID
from typing import List
from datetime import datetime, timedelta

from app.ai.agents.services.agent_orquestrator import create_agent_orquestrator

from app.logger import get_log

logger = get_log(__name__)

class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        skill_repository: SkillRepository,
        assessment_properties_repository: AssessmentPropertiesRepository
    ):
        self.session_repository = session_repository
        self.skill_repository = skill_repository
        self.assessment_properties_repository = assessment_properties_repository
    
    def has_owned_resource(self, session: Session, current_user: CurrentUser):
        if session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    def has_expired(self, session: Session) -> bool:
        return bool(session.expiration_at) and datetime.now() > session.expiration_at

    async def create_session(self, current_user: CurrentUser, session_input: SessionInput) -> SessionOutput:
        skill = self.skill_repository.get_by_id(session_input.skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{session_input.skill_id}' não encontrada"
            )
        
        if not skill.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill '{skill.name}' está inativa e não pode ser usada"
            )
        
        try:
            properties = self.assessment_properties_repository.get_or_create()
            expiration_at = datetime.now() + timedelta(minutes=properties.duration_minutes)

            session_create = Session(
                user_id=current_user.id,
                skill_id=session_input.skill_id,
                messages=[],
                expiration_at=expiration_at
            )
            session = self.session_repository.create(session_create)
            await self._start_session(session, current_user)
            return session.to_dict()
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao criar sessão: {str(e)}"
            )

    def get_session_by_id(self, current_user: CurrentUser, session_id: UUID) -> SessionOutput:
        session = self.session_repository.get_by_id(session_id)
        
        self.has_owned_resource(session, current_user)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        return session.to_dict()

    def list_sessions(self, current_user: CurrentUser, limit: int = 100) -> List[SessionOutput]:
        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite deve estar entre 1 e 1000"
            )
        
        sessions = self.session_repository.get_all_by_user_id(current_user.id, limit=limit)

        if not sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma Session encontrada"
            )

        return [session.to_dict() for session in sessions]

    def list_sessions_by_skill(self, current_user: CurrentUser, skill_id: UUID, limit: int = 100) -> List[SessionOutput]:
        skill = self.skill_repository.get_by_id(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )
        
        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite deve estar entre 1 e 1000"
            )
        
        sessions = self.session_repository.get_all_by_filters(
            user_id=current_user.id, skill_id=skill_id, limit=limit
        )

        if not sessions:
            return []

        return [session.to_dict() for session in sessions]

    async def add_message(
        self,
        current_user: CurrentUser,
        session_id: UUID,
        message_input: SessionMessageInput
    ) -> List[SessionMessageOutput]:
        if not message_input.text or not message_input.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O texto da mensagem não pode estar vazio"
            )
        
        session = self.session_repository.get_by_id(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )

        self.has_owned_resource(session, current_user)

        if self.has_expired(session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sessão expirada. Não é possível enviar novas mensagens"
            )
        
        try:
            logger.info(f"Salvando mensagem do usuário: {message_input.text[:50]}...")
            self.session_repository.add_message(
                session=session,
                message_input=message_input,
                user_type="user"
            )
            
            session = self.session_repository.get_by_id(session_id)
            
            logger.info("Processando com AgentOrquestrator...")
            orchestrator = create_agent_orquestrator(session, user_name=current_user.name)
            response = await orchestrator.get_response(message_input.text)
            
            saved_messages: list[dict] = []
            for pre in (response.pre_messages or []):
                logger.info(f"Salvando pre-mensagem do bot: {pre['text'][:50]}...")
                saved_messages.append(
                    self.session_repository.add_message(
                        session=session,
                        message_input=SessionMessageInput(text=pre["text"]),
                        user_type="bot",
                        params=pre.get("params") or {},
                    )
                )

            logger.info(f"Salvando mensagem do bot: {response.supervisor_message[:50]}...")
            saved_messages.append(
                self.session_repository.add_message(
                    session=session,
                    message_input=SessionMessageInput(text=response.supervisor_message),
                    user_type="bot",
                    params=response.params
                )
            )

            return [SessionMessageOutput(**m) for m in saved_messages]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar mensagem: {str(e)}"
            )
    
    async def _start_session(self, session: Session, current_user: CurrentUser = None):
        try:
            session_dict = session.to_dict(include_messages=True)
            if session_dict.get('messages'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sessão já foi iniciada"
                )
            
            logger.info("Iniciando sessão com saudação...")
            user_name = current_user.name if current_user else None
            orchestrator = create_agent_orquestrator(session, user_name=user_name)
            response = await orchestrator.get_response(user_message=None)
            
            logger.info(f"Salvando saudação: {response.supervisor_message[:50]}...")
            bot_message_input = SessionMessageInput(
                text=response.supervisor_message
            )
            
            self.session_repository.add_message(
                session=session,
                message_input=bot_message_input,
                user_type="bot",
                params=response.params
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao iniciar sessão: {str(e)}"
            )

    def delete_session(self, current_user: CurrentUser, session_id: UUID) -> None:
        session = self.session_repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )

        self.has_owned_resource(session, current_user)

        self.session_repository.delete(session_id)

    def get_session_messages(self, current_user: CurrentUser, session_id: UUID) -> List[SessionMessageOutput]:
        session = self.session_repository.get_by_id(session_id)

        self.has_owned_resource(session, current_user)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        return session.to_dict(include_messages=True)['messages']

    def get_session_message_count(self, current_user: CurrentUser, session_id: UUID) -> int:
        session = self.session_repository.get_by_id(session_id)

        self.has_owned_resource(session, current_user)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        return len(session.messages) if session.messages else 0


def get_session_service(
    session_repository: SessionRepository,
    skill_repository: SkillRepository,
    assessment_properties_repository: AssessmentPropertiesRepository
) -> SessionService:
    return SessionService(session_repository, skill_repository, assessment_properties_repository)