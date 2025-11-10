from pydantic_ai import Agent
from pydantic import BaseModel, Field
from app.logger import get_log

logger = get_log(__name__)


class AgentSkillEvaluatorResponse(BaseModel):
    classificacao: int = Field(description="intervalo", ge=-1, le=1)
    justificativa: str = Field(description="breve explicação")


class AgentSkillEvaluator:
    def __init__(
        self,
        runner: Agent,
        system_prompt: str,
        evaluation_prompt: str,
    ):
        self.runner = runner
        self.system_prompt = system_prompt
        self.evaluation_prompt = evaluation_prompt

        self.runner.system_prompt = system_prompt

    async def run_evaluation(self, evaluation_context: dict):

        objetivo = (
            "Identificar a capacidade de conectar tendências, inovação e "
            "entendimento do negócio para gerar valor a longo prazo. Uso: "
            "Selecionar talentos para áreas estratégicas, squads de inovação "
            "ou programas de transformação."
        )
        macrocompetencia = evaluation_context["current_specific_skill"]
        nivel_pergunta_aferidora = evaluation_context["current_proficiency_level"]
        pergunta_aferidora = evaluation_context["rubrics"][macrocompetencia][nivel_pergunta_aferidora]
        descricao_maturidade = evaluation_context["bloom_levels"][nivel_pergunta_aferidora]['descricao']
        nivel_pergunta_aferidora_abaixo = evaluation_context["bloom_levels"][nivel_pergunta_aferidora][
            "abaixo"
        ]
        descricao_maturidade_abaixo = evaluation_context["bloom_levels"][
            nivel_pergunta_aferidora_abaixo
        ]["descricao"]
        nivel_pergunta_aferidora_acima = evaluation_context["bloom_levels"][nivel_pergunta_aferidora][
            "acima"
        ]
        descricao_maturidade_acima = evaluation_context["bloom_levels"][nivel_pergunta_aferidora_acima][
            "descricao"
        ]

        self.runner.system_prompt = self.system_prompt.format(
            objetivo=objetivo,
            macrocompetencia=macrocompetencia,
            pergunta_aferidora=pergunta_aferidora,
            nivel_pergunta_aferidora=nivel_pergunta_aferidora,
            descricao_maturidade=descricao_maturidade,
            nivel_pergunta_aferidora_abaixo=nivel_pergunta_aferidora_abaixo,
            descricao_maturidade_abaixo=descricao_maturidade_abaixo,
            nivel_pergunta_aferidora_acima=nivel_pergunta_aferidora_acima,
            descricao_maturidade_acima=descricao_maturidade_acima,
        )

        user_prompt = self.evaluation_prompt.format(
            pergunta_aferidora=pergunta_aferidora, resposta_usuario=evaluation_context["user_message"]
        )

        logger.info(f"SkillEvaluator system prompt: {self.runner.system_prompt}")
        logger.info(f"SkillEvaluator user prompt: {user_prompt}")

        return await self.runner.run(user_prompt=user_prompt)
