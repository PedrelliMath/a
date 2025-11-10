from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session as DBSession
from app.models.skill import SkillInput, SkillOutput
from app.services.skill import SkillService, get_skill_service
from app.repository.skill import get_skill_repository
from app.database.db import get_db
from uuid import UUID

router = APIRouter(
    prefix="/skills",
    tags=["Skills"]
)

def get_skill_service_dep(
    db: DBSession = Depends(get_db)
) -> SkillService:
    repository = get_skill_repository(db)
    return get_skill_service(repository)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SkillOutput,
    summary="Criar nova skill",
    description="Cria uma nova skill. O nome da skill deve ser único."
)
def create_skill(
    skill_input: SkillInput,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.create_skill(skill_input)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Listar skills",
    description="Lista todas as skills com filtros opcionais."
)
def list_skills(
    active_only: bool = Query(
        False, 
        description="Filtrar apenas skills ativas"
    ),
    limit: int = Query(
        100, 
        ge=1, 
        le=1000, 
        description="Número máximo de skills a retornar"
    ),
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.list_skills(active_only=active_only, limit=limit)


@router.get(
    "/{skill_id}",
    status_code=status.HTTP_200_OK,
    summary="Buscar skill por ID",
    description="Retorna os detalhes de uma skill específica."
)
def get_skill(
    skill_id: UUID,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.get_skill_by_id(skill_id)


@router.get(
    "/name/{name}",
    status_code=status.HTTP_200_OK,
    summary="Buscar skill por nome",
    description="Retorna os detalhes de uma skill pelo seu nome."
)
def get_skill_by_name(
    name: str,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.get_skill_by_name(name)


@router.put(
    "/{skill_id}",
    status_code=status.HTTP_200_OK,
    summary="Atualizar skill",
    description="Atualiza todos os campos de uma skill existente."
)
def update_skill(
    skill_id: UUID,
    skill_input: SkillInput,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.update_skill(skill_id, skill_input)


@router.patch(
    "/{skill_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="Ativar skill",
    description="Ativa uma skill previamente desativada."
)
def activate_skill(
    skill_id: UUID,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.activate_skill(skill_id)


@router.patch(
    "/{skill_id}/deactivate",
    status_code=status.HTTP_200_OK,
    summary="Desativar skill",
    description="Desativa uma skill (soft delete). A skill não será deletada do banco."
)
def deactivate_skill(
    skill_id: UUID,
    service: SkillService = Depends(get_skill_service_dep)
):
    return service.deactivate_skill(skill_id)


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar skill permanentemente",
    description="Remove permanentemente uma skill do banco de dados. Use com cautela!"
)
def delete_skill(
    skill_id: UUID,
    service: SkillService = Depends(get_skill_service_dep)
):
    service.delete_skill(skill_id)