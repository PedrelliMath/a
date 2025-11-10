from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session as DBSession
from app.models.evaluation import EvaluationOutput
from app.services.evaluation import EvaluationService, get_evaluation_service
from app.repository.evaluation import get_evaluation_repository
from app.repository.session import get_session_repository
from app.repository.skill import get_skill_repository
from app.database.db import get_db
from uuid import UUID

router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluations"]
)

def get_evaluation_service_dep(
    db: DBSession = Depends(get_db)
) -> EvaluationService:
    evaluation_repository = get_evaluation_repository(db)
    session_repository = get_session_repository(db)
    skill_repository = get_skill_repository(db)
    return get_evaluation_service(
        evaluation_repository, session_repository, skill_repository
    )

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[EvaluationOutput],
    summary="Lista todas as Avaliações",
    description="Lista todas as Avaliações registradas ordenada pela mais recente"
)
def get_all_evaluations(
    service: EvaluationService = Depends(get_evaluation_service_dep)
):
    return service.get_evaluations()

@router.get(
    "/{evaluation_id}",
    status_code=status.HTTP_200_OK,
    response_model=EvaluationOutput,
    summary="Lista uma Avaliação pelo ID",
    description="Lista uma Avaliação pelo ID caso exista"
)
def get_evaluation_by_session_id(
    evaluation_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service_dep)
):
    return service.get_evaluation_by_id(evaluation_id)

@router.get(
    "/skill/{skill_id}",
    status_code=status.HTTP_200_OK,
    response_model=EvaluationOutput,
    summary="Lista Avaliações pelo ID da skill",
    description="Lista todas as Avaliações pelo ID da skill de forma ordenada"
)
def get_evaluation_by_skill_id(
    skill_id: UUID,
    limit: int = Query(
        100, 
        ge=1, 
        le=1000, 
        description="Número máximo de avaliações a retornar"
    ),
    service: EvaluationService = Depends(get_evaluation_service_dep)
):
    return service.list_evaluations_by_skill(skill_id, limit)

@router.get(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=EvaluationOutput,
    summary="Lista uma Avaliação pelo ID da sessão",
    description="Lista uma Avaliação pelo ID da sessão caso esteja finalizada"
)
def get_evaluation_by_session_id(
    session_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service_dep)
):
    return service.get_evaluation_by_session_id(session_id)