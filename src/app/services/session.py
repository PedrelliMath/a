from fastapi import HTTPException, status
from app.models.session import Session, SessionInput, SessionOutput, SessionMessageInput, SessionMessageOutput
from app.models.current_user import CurrentUser
from app.repository.session import SessionRepository
from app.repository.skill import SkillRepository
from uuid import UUID
from typing import List

from app.ai.agents.services.agent_orquestrator import create_agent_orquestrator

from app.logger import get_log

logger = get_log(__name__)

class SessionService:
    def __init__(self, session_repository: SessionRepository, skill_repository: SkillRepository):
        self.session_repository = session_repository
        self.skill_repository = skill_repository
    
    def has_owned_resource(self, session: Session, current_user: CurrentUser):
        if session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

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

            session_create = Session(user_id=current_user.id, skill_id=session_input.skill_id, messages=[])
            session = self.session_repository.create(session_create)
            await self._start_session(session)
            return session.to_dict()
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao criar sessão: {str(e)}"
            )

    def get_session_by_id(self, current_user: CurrentUser, session_id: UUID) -> SessionOutput:
        """
        Busca uma sessão por ID.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            SessionOutput: Sessão encontrada
            
        Raises:
            HTTPException: 404 se a sessão não for encontrada
        """
        session = self.session_repository.get_by_id(session_id)
        
        self.has_owned_resource(session, current_user)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        return session.to_dict()

    def list_sessions(self, current_user: CurrentUser, limit: int = 100) -> List[SessionOutput]:
        """
        Lista todas as sessões ordenadas por data de criação (mais recentes primeiro).
        
        Args:
            limit: Número máximo de sessões a retornar
            
        Returns:
            List[SessionOutput]: Lista de sessões
        """
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
        """
        Lista todas as sessões de uma skill específica.
        
        Args:
            skill_id: ID da skill
            limit: Número máximo de sessões a retornar
            
        Returns:
            List[SessionOutput]: Lista de sessões da skill
            
        Raises:
            HTTPException: 404 se a skill não existir
        """
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
        """
        Adiciona mensagem do usuário e obtém resposta do bot
        
        Args:
            session_id: UUID da sessão
            message_input: Mensagem do usuário
            params: Parâmetros adicionais (opcional)
            
        Returns:
            dict com mensagem do bot e metadados
            
        Fluxo:
        1. Validar input
        2. Buscar session
        3. Salvar mensagem do usuário
        4. Processar com AgentOrquestrator
        5. Salvar mensagem do bot
        6. Retornar resposta
        """
        # Validar input
        if not message_input.text or not message_input.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O texto da mensagem não pode estar vazio"
            )
        
        # Buscar session
        session = self.session_repository.get_by_id(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )

        self.has_owned_resource(session, current_user)
        
        try:
            # 1. Salvar mensagem do usuário
            logger.info(f"Salvando mensagem do usuário: {message_input.text[:50]}...")
            self.session_repository.add_message(
                session=session,
                message_input=message_input,
                user_type="user"
            )
            
            # 2. Recarregar session para pegar a mensagem do usuário
            session = self.session_repository.get_by_id(session_id)
            
            # 3. Criar orquestrador e processar
            logger.info("Processando com AgentOrquestrator...")
            orchestrator = create_agent_orquestrator(session)
            response = await orchestrator.get_response(message_input.text)
            
            # 4. Salvar pre-mensagens do bot (ex: frase de transicao entre topicos)
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

            # 5. Salvar mensagem principal do bot
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
    
    async def _start_session(self, session: Session):
        """
        Inicia uma sessão com saudação do bot
        
        Args:
            session_id: sessão
            
        Returns:
            dict com mensagem de saudação e metadados
        """   
        try:
            # Verificar se já tem mensagens
            session_dict = session.to_dict(include_messages=True)
            if session_dict.get('messages'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sessão já foi iniciada"
                )
            
            # Criar orquestrador e processar sem mensagem = saudação
            logger.info("Iniciando sessão com saudação...")
            orchestrator = create_agent_orquestrator(session)
            response = await orchestrator.get_response(user_message=None)
            
            # Salvar saudação do bot
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
        """
        Deleta permanentemente uma sessão do banco de dados.
        
        Args:
            session_id: ID da sessão a ser deletada
            
        Raises:
            HTTPException: 404 se a sessão não for encontrada
        """
        session = self.session_repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )

        self.has_owned_resource(session, current_user)

        self.session_repository.delete(session_id)

    def get_session_messages(self, current_user: CurrentUser, session_id: UUID) -> List[SessionMessageOutput]:
        """
        Retorna todas as mensagens de uma sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            List[SessionMessageOutput]: Lista de mensagens da sessão
            
        Raises:
            HTTPException: 404 se a sessão não for encontrada
        """
        session = self.session_repository.get_by_id(session_id)

        self.has_owned_resource(session, current_user)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        return session.to_dict(include_messages=True)['messages']

    def get_session_message_count(self, current_user: CurrentUser, session_id: UUID) -> int:
        """
        Retorna o número de mensagens em uma sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            int: Número de mensagens
            
        Raises:
            HTTPException: 404 se a sessão não for encontrada
        """
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
    skill_repository: SkillRepository
) -> SessionService:
    """
    Factory function para criar uma instância do SessionService.
    
    Args:
        session_repository: Instância do SessionRepository
        skill_repository: Instância do SkillRepository
        
    Returns:
        SessionService: Instância do serviço
    """
    return SessionService(session_repository, skill_repository)