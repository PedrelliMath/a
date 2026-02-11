from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)


class AgentMessageValidatorResponse(BaseModel):
    is_valid: bool = Field(
        ...,
        description="""
        valor booleano true para resposta 
        valida e false para inválida
        """,
    )
    explicacao: str | None = Field(
        default=None,
        description="""
            Justificativa objetiva e técnica, 
            explicando o porquê da decisão para
            respostas inválidas.
        """,
    )


class AgentMessageValidator:
    def __init__(
        self,
        runner: Agent,
        system_prompt: str,
        validation_prompt: str,
    ):
        self.runner = runner
        self.system_prompt = system_prompt
        self.validation_prompt = validation_prompt

        self.runner.system_prompt = system_prompt

    @track_helicone(agent_type="message_validator")
    async def run_validation(self, validation_context: dict):
        final_prompt = self.validation_prompt.format(
            question=validation_context['question'],
            answer=validation_context['user_message'],
        )
        logger.info(f"run_validation final_prompt:\n{final_prompt}")
        result = await self.runner.run(user_prompt=final_prompt)
        return result
