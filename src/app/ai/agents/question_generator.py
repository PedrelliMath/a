from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.ai.agents.prompts.question_generator import (
    system_prompt_generation,
    system_prompt_regeneration,
)
from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)


class AgentQuestionGeneratorResponse(BaseModel):
    pergunta: str = Field(
        description="pergunta gerada pelo agente gerador de perguntas"
    )


class AgentQuestionGenerator:
    """
    Gerador de perguntas.

    Geração e regeneração são dois agentes distintos, cada um com as suas
    `instructions`. Antes o mesmo objeto tinha o `system_prompt` reatribuído
    em runtime a cada chamada — atribuição que não tinha efeito nenhum sobre o
    modelo (`Agent.system_prompt` é um decorator, não um campo) e que era
    frágil sob concorrência.
    """

    def __init__(
        self,
        model: str,
        generation_prompt: str,
        regeneration_prompt: str,
    ):
        self.generation_prompt = generation_prompt
        self.regeneration_prompt = regeneration_prompt

        self.gerador = Agent(
            model=model,
            output_type=AgentQuestionGeneratorResponse,
            instructions=system_prompt_generation,
        )
        self.regerador = Agent(
            model=model,
            output_type=AgentQuestionGeneratorResponse,
            instructions=system_prompt_regeneration,
        )
        # Usado pela observabilidade (track_helicone) para extrair o modelo.
        self.runner = self.gerador

    @track_helicone(agent_type="question_generator")
    async def run_generation(self, generation_context: dict):
        final_prompt = self.generation_prompt.format(
            proficiency_level=generation_context["current_proficiency_level"],
            specific_skill=generation_context["current_specific_skill"],
            joined_questions="\n".join(
                f"- {q}" for q in generation_context["current_question_set"]
            ),
        )
        logger.info(f"run_generation final_prompt:\n{final_prompt}")
        return await self.gerador.run(user_prompt=final_prompt)

    @track_helicone(agent_type="question_generator")
    async def run_regeneration(self, context: dict):
        final_prompt = self.regeneration_prompt.format(
            past_question=context["past_question"],
            past_answer=context["past_answer"],
            intent=context["intent"],
            focus=context["focus"],
            constraints=context["constraints"],
        )
        logger.info(f"run_regeneration final_prompt:\n{final_prompt}")
        return await self.regerador.run(user_prompt=final_prompt)
