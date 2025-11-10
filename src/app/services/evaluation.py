from fastapi import HTTPException, status
from app.models.evaluation import EvaluationInput, EvaluationOutput
from app.repository.evaluation import EvaluationRepository
from app.repository.session import SessionRepository
from app.repository.skill import SkillRepository
from uuid import UUID
from typing import Optional


class EvaluationService:
    def __init__(
        self, 
        evaluation_repository: EvaluationRepository,
        session_repository: SessionRepository,
        skill_repository: SkillRepository
    ):
        self.evaluation_repository = evaluation_repository
        self.session_repository = session_repository
        self.skill_repository = skill_repository

    def create_evaluation(self, evaluation_input: EvaluationInput) -> EvaluationOutput:
        """
        Cria uma nova avaliação vinculada a uma sessão.
        
        Args:
            evaluation_input: Dados da avaliação a ser criada (session_id)
            
        Returns:
            EvaluationOutput: Avaliação criada
            
        Raises:
            HTTPException: 404 se a sessão não existir
            HTTPException: 409 se já existe uma avaliação para esta sessão
            HTTPException: 500 para outros erros
        """
        # Converte string para UUID
        try:
            session_uuid = UUID(evaluation_input.session_id)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ID de sessão inválido: '{evaluation_input.session_id}'"
            )
        
        # Verifica se a sessão existe
        session = self.session_repository.get_by_id(session_uuid)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{evaluation_input.session_id}' não encontrada"
            )
        
        # Verifica se já existe uma avaliação para esta sessão
        existing_evaluation = self.evaluation_repository.get_by_session_id(session_uuid)
        
        if existing_evaluation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe uma avaliação para a sessão '{evaluation_input.session_id}'"
            )
        
        try:
            evaluation = self.evaluation_repository.create(evaluation_input)
            return evaluation.to_output()
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao criar avaliação: {str(e)}"
            )

    def get_evaluations(self) -> list[EvaluationOutput]:
        """
        Busca todas as avaliações.
            
        Returns:
            List[EvaluationOutput]: Avaliações encontrada
            
        Raises:
            HTTPException: 404 se não houver avaliações
        """
        evaluations = self.evaluation_repository.get_all()
        
        if not evaluations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma Avaliação encontrada" 
            )
        
        return [evaluation.to_dict() for evaluation in evaluations]

    def get_evaluation_by_id(self, evaluation_id: UUID) -> EvaluationOutput:
        """
        Busca uma avaliação por ID.
        
        Args:
            evaluation_id: ID da avaliação
            
        Returns:
            EvaluationOutput: Avaliação encontrada
            
        Raises:
            HTTPException: 404 se a avaliação não for encontrada
        """
        evaluation = self.evaluation_repository.get_by_id(evaluation_id)
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Avaliação com ID '{evaluation_id}' não encontrada"
            )
        
        return evaluation.to_output()

    def get_evaluation_by_session_id(self, session_id: UUID) -> EvaluationOutput:
        """
        Busca uma avaliação pelo ID da sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            EvaluationOutput: Avaliação encontrada
            
        Raises:
            HTTPException: 404 se a sessão não existir
            HTTPException: 404 se não houver avaliação para esta sessão
        """
        # Verifica se a sessão existe
        session = self.session_repository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada"
            )
        
        evaluation = self.evaluation_repository.get_by_session_id(session_id)
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma avaliação encontrada para a sessão '{session_id}'"
            )
        
        return evaluation.to_output()
    
    def list_evaluations_by_skill(self, skill_id: UUID, limit: int = 100) -> list[EvaluationOutput]:
        """
        Lista todas as avaliações de uma skill específica.
        
        Args:
            skill_id: ID da skill
            limit: Número máximo de avaliações a retornar
            
        Returns:
            List[EvaluationOutput]: Lista de sessões da skill
            
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
        
        evaluations = self.evaluation_repository.get_by_skill_id(skill_id, limit=limit)

        if not evaluations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma avaliação encontrada para a skill {skill_id}'"
            )

        return [evaluation.to_dict() for evaluation in evaluations]


    def delete_evaluation(self, evaluation_id: UUID) -> None:
        """
        Deleta permanentemente uma avaliação do banco de dados.
        
        Args:
            evaluation_id: ID da avaliação a ser deletada
            
        Raises:
            HTTPException: 404 se a avaliação não for encontrada
        """
        success = self.evaluation_repository.delete(evaluation_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Avaliação com ID '{evaluation_id}' não encontrada"
            )


def get_evaluation_service(
    evaluation_repository: EvaluationRepository,
    session_repository: SessionRepository,
    skill_repository: SkillRepository
) -> EvaluationService:
    """
    Factory function para criar uma instância do EvaluationService.
    
    Args:
        evaluation_repository: Instância do EvaluationRepository
        session_repository: Instância do SessionRepository
        skill_repository: Instância do SkillRepository
        
    Returns:
        EvaluationService: Instância do serviço
    """
    return EvaluationService(evaluation_repository, session_repository, skill_repository)