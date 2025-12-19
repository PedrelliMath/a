from pydantic_ai import Agent
from pydantic import BaseModel, Field

from app.logger import get_log

logger = get_log(__name__)

class AgentSupervisorResponse(BaseModel):
    message: str = Field(description="mensagem do agente supervisor")


class AgentSupervisor:
    def __init__(
        self,
        runner: Agent,
        system_prompt: str,
        retype_prompt: str,
        close_prompt: str,
        message_prompt: str,
        greeting_prompt: str,
    ):
        self.runner = runner
        self.system_prompt = system_prompt
        self.retype_prompt = retype_prompt
        self.close_prompt = close_prompt
        self.message_prompt = message_prompt
        self.greeting_prompt = greeting_prompt

        self.runner.system_prompt = system_prompt

    async def run_end(self, end_context: dict):
        final_prompt = self.message_prompt.format(
            message_history=end_context["message_history"],
            current_subject=end_context["current_subject"],
            generated_question=end_context["generated_question"],
        )

        logger.info(F"PROMPT SUPERVISOR: {final_prompt}")

        return await self.runner.run(user_prompt=final_prompt)

    async def run_retype(self, retype_context: dict):
        final_prompt = self.retype_prompt.format(
            message_history=retype_context['message_history'],
        )
        return await self.runner.run(user_prompt=final_prompt)

    async def run_close(self, close_context: dict):
        final_prompt = self.close_prompt.format(
            message_history=close_context["message_history"],
        )
        return await self.runner.run(user_prompt=final_prompt)

    async def run_greeting(self, greeting_context: dict):
        final_prompt = self.greeting_prompt.format(
            skill_name=greeting_context['skill_name'],
            subjects=greeting_context['subjects'],
            user_name=greeting_context['user_name'],
            first_question=greeting_context['first_question']
        )
        return await self.runner.run(user_prompt=final_prompt)
