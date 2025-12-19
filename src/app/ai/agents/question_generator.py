from pydantic_ai import Agent
from pydantic import BaseModel, Field
from app.ai.agents.prompts.question_generator import system_prompt_generation
from app.ai.agents.prompts.question_generator import system_prompt_regeneration

from app.logger import get_log

logger = get_log(__name__)


class AgentQuestionGeneratorResponse(BaseModel):
    pergunta: str = Field(
        description="pergunta gerada pelo agente gerador de perguntas"
    )


class AgentQuestionGenerator:
    def __init__(
        self,
        runner: Agent,
        generation_prompt: str,
        regeneration_prompt: str,
        system_prompt: str | None = None,
    ):
        self.runner = runner
        self.system_prompt = system_prompt
        self.generation_prompt = generation_prompt
        self.regeneration_prompt = regeneration_prompt

        self.runner.system_prompt = system_prompt

    async def run_generation(self, generation_context: dict):

        self.runner.system_prompt = system_prompt_generation

        final_prompt = self.generation_prompt.format(
            proficiency_level=generation_context["current_proficiency_level"],
            specific_skill=generation_context["current_specific_skill"],
            joined_questions="\n".join(f"- {q}" for q in generation_context['current_question_set'])
        )
        logger.info(f"run_generation final_prompt:\n{final_prompt}")
        return await self.runner.run(user_prompt=final_prompt)

    async def run_regeneration(self, context: dict):

        self.runner.system_prompt = system_prompt_regeneration

        final_prompt = self.regeneration_prompt.format(
            past_question=context['bot_message'],
            past_answer=context['user_response'],
            answer_validator_feedback=context['validator_feedback']
        )
        logger.info(f"run_regeneration final_prompt:\n{final_prompt}")
        return await self.runner.run(user_prompt=final_prompt)
