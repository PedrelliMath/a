from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DBSession
from app.models.assessment_properties import AssessmentPropertiesInput
from app.services.assessment_properties import AssessmentPropertiesService, get_assessment_properties_service
from app.repository.assessment_properties import get_assessment_properties_repository
from app.database.db import get_db
from app.auth.auth import get_current_user, oauth2_scheme
from app.models.current_user import CurrentUser


router = APIRouter(
    prefix="/assessment-properties",
    tags=["Assessment Properties"],
    dependencies=[Depends(oauth2_scheme)]
)


def get_assessment_properties_service_dep(
    db: DBSession = Depends(get_db)
) -> AssessmentPropertiesService:
    assessment_properties_repository = get_assessment_properties_repository(db)
    return get_assessment_properties_service(assessment_properties_repository)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    #response_model=AssessmentPropertiesOutput,
    summary="Busca as configurações do assessment",
    description="Retorna as configurações globais do assessment, criando com valores padrão caso não existam"
)
def get_assessment_properties(
    service: AssessmentPropertiesService = Depends(get_assessment_properties_service_dep),
    current_user: CurrentUser = Depends(get_current_user)
):
    return service.get_properties(current_user)


@router.put(
    "",
    status_code=status.HTTP_200_OK,
    #response_model=AssessmentPropertiesOutput,
    summary="Atualiza as configurações do assessment",
    description="Atualiza o tempo do assessment em minutos"
)
def update_assessment_properties(
    data: AssessmentPropertiesInput,
    service: AssessmentPropertiesService = Depends(get_assessment_properties_service_dep),
    current_user: CurrentUser = Depends(get_current_user)
):
    return service.update_properties(current_user, data)