from fastapi import HTTPException, status
from app.models.evaluation import EvaluationInput, EvaluationOutput
from app.repository.evaluation import EvaluationRepository
from app.repository.session import SessionRepository
from app.repository.skill import SkillRepository
from uuid import UUID
from typing import Optional
from app.models.current_user import CurrentUser
from app.models.session import Session


class EvaluationService:
    def __init__(
        self,
        evaluation_repository: EvaluationRepository,
        session_repository: SessionRepository,
        skill_repository: SkillRepository,
    ):
        self.evaluation_repository = evaluation_repository
        self.session_repository = session_repository
        self.skill_repository = skill_repository

    def has_owned_resource(self, session: Session, current_user: CurrentUser):
        if session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    def _extract_iterations_from_session(self, session):
        """
        Constrói a lista de iterations a partir das mensagens da sessão.
        Respostas inválidas do usuário são concatenadas com a resposta válida
        final em um único campo 'response'.
        Perguntas puladas (skip) são registradas com response=None e skipped=True.
        """
        iterations = []
        pending_question = None
        pending_responses = []

        def _flush_iteration(bot_params):
            """Fecha a iteração pendente e adiciona à lista."""
            if not pending_question:
                return

            is_skip = bot_params.get("flow", {}).get("type") == "skip"
            achieved = bot_params.get("skill_evaluator", {}).get("achieved_level")

            if is_skip:
                iterations.append({
                    "question": pending_question["question"],
                    "response": None,
                    "expected_bloom_level": pending_question["expected_bloom_level"],
                    "achieved_bloom_level": None,
                    "macro": pending_question["macro"],
                    "skipped": True,
                })
            elif pending_responses:
                iterations.append({
                    "question": pending_question["question"],
                    "response": " | ".join(pending_responses),
                    "expected_bloom_level": pending_question["expected_bloom_level"],
                    "achieved_bloom_level": achieved,
                    "macro": pending_question["macro"],
                    "skipped": False,
                })

        for msg in session.messages:
            user_type = msg.get("user_type")
            params = msg.get("params", {})

            is_valid = params.get("message_validator", {}).get("is_valid", False)
            is_greeting = params.get("supervisor", {}).get("action") == "greeting"
            is_closing = params.get("supervisor", {}).get("action") == "close"
            is_skip = params.get("flow", {}).get("type") == "skip"

            if user_type == "bot" and not is_valid and not is_greeting and not is_closing and not is_skip:
                continue

            if user_type == "bot":
                if is_greeting:
                    pending_question = {
                        "question": msg.get("text"),
                        "expected_bloom_level": params.get("new_proficiency_level"),
                        "macro": params.get("new_specific_skill"),
                    }
                    pending_responses = []

                elif is_closing:
                    _flush_iteration(params)
                    pending_question = None
                    pending_responses = []

                else:
                    # Nova pergunta — fecha a anterior
                    _flush_iteration(params)
                    pending_question = {
                        "question": msg.get("text"),
                        "expected_bloom_level": params.get("new_proficiency_level"),
                        "macro": params.get("new_specific_skill"),
                    }
                    pending_responses = []

            elif user_type == "user":
                pending_responses.append(msg.get("text", ""))

        return iterations

    def create_evaluation(self, current_user: CurrentUser, session_id) -> EvaluationOutput:
        session = self.session_repository.get_by_id(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada",
            )

        self.has_owned_resource(session, current_user)

        existing_evaluation = self.evaluation_repository.get_by_session_id(session.id)

        if existing_evaluation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe uma avaliação para a sessão '{session.id}'",
            )

        iterations = self._extract_iterations_from_session(session)

        try:
            evaluation = self.evaluation_repository.create(session, iterations)
            return evaluation.to_dict()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao criar avaliação: {str(e)}",
            )

    def get_evaluations(self, current_user: CurrentUser) -> list[EvaluationOutput]:
        evaluations = self.evaluation_repository.get_all(current_user.id)

        if not evaluations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhuma Avaliação encontrada",
            )

        return [evaluation.to_dict() for evaluation in evaluations]

    def get_evaluation_by_id(self, current_user: CurrentUser, evaluation_id: UUID) -> EvaluationOutput:
        evaluation = self.evaluation_repository.get_by_id(evaluation_id)

        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Avaliação com ID '{evaluation_id}' não encontrada",
            )

        self.has_owned_resource(evaluation.session, current_user)

        return evaluation.to_dict()

    def get_evaluation_by_session_id(self, current_user: CurrentUser, session_id: UUID) -> EvaluationOutput:
        session = self.session_repository.get_by_id(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão com ID '{session_id}' não encontrada",
            )

        self.has_owned_resource(session, current_user)

        evaluation = self.evaluation_repository.get_by_session_id(session_id)

        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma avaliação encontrada para a sessão '{session_id}'",
            )

        return evaluation.to_dict()

    def list_evaluations_by_skill(
        self, current_user: CurrentUser, skill_id: UUID, limit: int = 100
    ) -> list[EvaluationOutput]:
        skill = self.skill_repository.get_all(current_user.id, skill_id=skill_id)

        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill com ID '{skill_id}' não encontrada",
            )

        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite deve estar entre 1 e 1000",
            )

        evaluations = self.evaluation_repository.get_by_skill_id(skill_id, limit=limit)

        if not evaluations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhuma avaliação encontrada para a skill {skill_id}'",
            )

        return [evaluation.to_dict() for evaluation in evaluations]

    def delete_evaluation(self, current_user: CurrentUser, evaluation_id: UUID) -> None:
        evaluation = self.evaluation_repository.get_by_id(evaluation_id)

        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Avaliação com ID '{evaluation_id}' não encontrada",
            )

        self.has_owned_resource(evaluation.session, current_user)
        self.evaluation_repository.delete(evaluation_id)


def get_evaluation_service(
    evaluation_repository: EvaluationRepository,
    session_repository: SessionRepository,
    skill_repository: SkillRepository,
) -> EvaluationService:
    return EvaluationService(evaluation_repository, session_repository, skill_repository)