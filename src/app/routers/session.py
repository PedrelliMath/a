from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session as DBSession
from app.models.session import SessionInput, SessionOutput, SessionMessageInput, SessionMessageOutput
from app.services.session import SessionService, get_session_service
from app.repository.session import get_session_repository
from app.repository.skill import get_skill_repository
from app.database.db import get_db
from uuid import UUID

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"]
)

def get_session_service_dep(
    db: DBSession = Depends(get_db)
) -> SessionService:
    session_repo = get_session_repository(db)
    skill_repo = get_skill_repository(db)
    return get_session_service(session_repo, skill_repo)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionOutput,
    summary="Criar nova sessão",
    description="Cria uma nova sessão vinculada a uma skill ativa."
)
async def create_session(
    session_input: SessionInput,
    service: SessionService = Depends(get_session_service_dep)
):
    return await service.create_session(session_input)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[SessionOutput],
    summary="Listar sessões",
    description="Lista todas as sessões ordenadas por data de criação (mais recentes primeiro)."
)
def list_sessions(
    limit: int = Query(
        100, 
        ge=1, 
        le=1000, 
        description="Número máximo de sessões a retornar"
    ),
    service: SessionService = Depends(get_session_service_dep)
):
    return service.list_sessions(limit=limit)


@router.get(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=SessionOutput,
    summary="Buscar sessão por ID",
    description="Retorna os detalhes de uma sessão"
)
def get_session(
    session_id: UUID,
    service: SessionService = Depends(get_session_service_dep)
):
    return service.get_session_by_id(session_id)


@router.get(
    "/skill/{skill_id}",
    status_code=status.HTTP_200_OK,
    response_model=list[SessionOutput],
    summary="Listar sessões por skill",
    description="Lista todas as sessões vinculadas a uma skill específica."
)
def list_sessions_by_skill(
    skill_id: UUID,
    limit: int = Query(
        100, 
        ge=1, 
        le=1000, 
        description="Número máximo de sessões a retornar"
    ),
    service: SessionService = Depends(get_session_service_dep)
):
    return service.list_sessions_by_skill(skill_id, limit=limit)


@router.post(
    "/{session_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionMessageOutput,
    summary="Adicionar mensagem à sessão",
    description="Adiciona uma nova mensagem a uma sessão existente."
)
async def add_message(
    session_id: UUID,
    message_input: SessionMessageInput,
    service: SessionService = Depends(get_session_service_dep)
):
    return await service.add_message(session_id, message_input)

@router.get(
    "/{session_id}/messages",
    status_code=status.HTTP_200_OK,
    response_model=list[SessionMessageOutput],
    summary="Listar mensagens da sessão",
    description="Retorna todas as mensagens de uma sessão."
)
def get_session_messages(
    session_id: UUID,
    service: SessionService = Depends(get_session_service_dep)
):
    return service.get_session_messages(session_id)


@router.get(
    "/{session_id}/messages/count",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, int],
    summary="Contar mensagens",
    description="Retorna o número total de mensagens em uma sessão."
)
def get_message_count(
    session_id: UUID,
    service: SessionService = Depends(get_session_service_dep)
):
    count: int  = service.get_session_message_count(session_id)
    return {"count": count}


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar sessão",
    description="Remove permanentemente uma sessão e todas as suas mensagens do banco de dados."
)
def delete_session(
    session_id: UUID,
    service: SessionService = Depends(get_session_service_dep)
):
    service.delete_session(session_id)