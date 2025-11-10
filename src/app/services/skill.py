from fastapi import HTTPException, status
from app.models.skill import SkillInput, SkillOutput
from app.repository.skill import SkillRepository
from uuid import UUID
from typing import List

class SkillService:
    def __init__(self, repository: SkillRepository):
        self.repository = repository

    def create_skill(self, skill_input: SkillInput) -> SkillOutput:
        existing_skill = self.repository.get_by_name(skill_input.name)
        
        if existing_skill:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill com o nome '{skill_input.name}' já existe"
            )
        
        try:
            skill = self.repository.create(skill_input)
            return skill.to_dict()
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao criar skill: {str(e)}"
            )

    def get_skill_by_id(self, skill_id: UUID) -> SkillOutput:
        """
        Busca uma skill por ID.
        
        Args:
            skill_id: ID da skill
            
        Returns:
            SkillOutput: Skill encontrada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
        """
        skill = self.repository.get_by_id(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )
        
        return skill.to_dict()

    def get_skill_by_name(self, name: str) -> SkillOutput:
        """
        Busca uma skill por nome.
        
        Args:
            name: Nome da skill
            
        Returns:
            SkillOutput: Skill encontrada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
        """
        skill = self.repository.get_by_name(name)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com nome '{name}' não encontrada"
            )
        
        return skill.to_dict()

    def list_skills(self, active_only: bool = False, limit: int = 100) -> List[SkillOutput]:
        """
        Lista todas as skills.
        
        Args:
            active_only: Se True, retorna apenas skills ativas
            limit: Número máximo de skills a retornar
            
        Returns:
            List[SkillOutput]: Lista de skills
        """
        skills = self.repository.get_all(active_only=active_only, limit=limit)
        return [skill.to_dict() for skill in skills]

    def update_skill(self, skill_id: UUID, skill_input: SkillInput) -> SkillOutput:
        """
        Atualiza uma skill existente.
        
        Args:
            skill_id: ID da skill a ser atualizada
            skill_input: Novos dados da skill
            
        Returns:
            SkillOutput: Skill atualizada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
            HTTPException: 409 se já existe outra skill com o mesmo nome
        """
        # Verifica se a skill existe
        existing_skill = self.repository.get_by_id(skill_id)
        
        if not existing_skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )
        
        # Verifica se o novo nome já existe em outra skill
        if skill_input.name != existing_skill.name:
            skill_with_same_name = self.repository.get_by_name(skill_input.name)
            
            if skill_with_same_name and skill_with_same_name.id != skill_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Skill com o nome '{skill_input.name}' já existe"
                )
        
        try:
            updated_skill = self.repository.update(skill_id, skill_input)
            
            if not updated_skill:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Skill com ID '{skill_id}' não encontrada"
                )
            
            return updated_skill.to_dict()
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao atualizar skill: {str(e)}"
            )

    def delete_skill(self, skill_id: UUID) -> None:
        """
        Deleta permanentemente uma skill do banco de dados.
        
        Args:
            skill_id: ID da skill a ser deletada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
        """
        success = self.repository.delete(skill_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )

    def deactivate_skill(self, skill_id: UUID) -> SkillOutput:
        """
        Desativa uma skill (soft delete).
        
        Args:
            skill_id: ID da skill a ser desativada
            
        Returns:
            SkillOutput: Skill desativada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
        """
        skill = self.repository.deactivate(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )
        
        return skill.to_dict()

    def activate_skill(self, skill_id: UUID) -> SkillOutput:
        """
        Ativa uma skill previamente desativada.
        
        Args:
            skill_id: ID da skill a ser ativada
            
        Returns:
            SkillOutput: Skill ativada
            
        Raises:
            HTTPException: 404 se a skill não for encontrada
        """
        skill = self.repository.activate(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada"
            )
        
        return skill.to_dict()


def get_skill_service(repository: SkillRepository) -> SkillService:
    """
    Factory function para criar uma instância do SkillService.
    
    Args:
        repository: Instância do SkillRepository
        
    Returns:
        SkillService: Instância do serviço
    """
    return SkillService(repository)