from fastapi import HTTPException, status
from app.models.assessment_properties import AssessmentPropertiesInput, AssessmentPropertiesOutput
from app.repository.assessment_properties import AssessmentPropertiesRepository
from app.models.current_user import CurrentUser


class AssessmentPropertiesService:
    def __init__(self, assessment_properties_repository: AssessmentPropertiesRepository):
        self.assessment_properties_repository = assessment_properties_repository

    def get_properties(self, current_user: CurrentUser) -> AssessmentPropertiesOutput:
        try:
            properties = self.assessment_properties_repository.get_or_create()
            return properties.to_dict()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao buscar configurações do assessment: {str(e)}",
            )

    def update_properties(
        self, current_user: CurrentUser, data: AssessmentPropertiesInput
    ) -> AssessmentPropertiesOutput:
        if data.duration_minutes < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O tempo do assessment deve ser maior que 0",
            )

        try:
            properties = self.assessment_properties_repository.update_duration(data.duration_minutes)
            return properties.to_dict()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao atualizar configurações do assessment: {str(e)}",
            )


def get_assessment_properties_service(
    assessment_properties_repository: AssessmentPropertiesRepository,
) -> AssessmentPropertiesService:
    return AssessmentPropertiesService(assessment_properties_repository)