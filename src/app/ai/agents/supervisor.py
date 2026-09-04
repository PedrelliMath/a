from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)


class AgentSupervisorResponse(BaseModel):
    message: str = Field(description="mensagem do agente supervisor")


@dataclass
class SupervisorDeps:
    """Contexto do turno usado pelas instructions dinâmicas do supervisor."""

    topico_atual: str = ""
    ponto_forte_anterior: str | None = None
    trocou_de_topico: bool = False


class AgentSupervisor:
    """
    Supervisor da conversa.

    O prompt persistente (identidade, postura, formato, limites) é registrado
    como `instructions`, e não como `system_prompt`. Instructions são
    reaplicadas em toda run, inclusive quando há `message_history`, então as
    regras de conduta valem em todos os caminhos (greeting, turno, desvio,
    retype e close) e não só no turno normal.
    """

    def __init__(
        self,
        model: str,
        system_prompt: str,
        retype_prompt: str,
        close_prompt: str,
        turn_prompt: str,
        greeting_prompt: str,
        off_topic_prompt: str,
    ):
        self.system_prompt = system_prompt
        self.retype_prompt = retype_prompt
        self.close_prompt = close_prompt
        self.turn_prompt = turn_prompt
        self.greeting_prompt = greeting_prompt
        self.off_topic_prompt = off_topic_prompt

        self.runner = Agent(
            model=model,
            deps_type=SupervisorDeps,
            output_type=AgentSupervisorResponse,
            instructions=system_prompt,
        )

        self.runner.instructions(_reconhecimento)
        self.runner.instructions(_transicao)

    async def _run(self, prompt: str, deps: SupervisorDeps | None = None):
        return await self.runner.run(user_prompt=prompt, deps=deps or SupervisorDeps())

    @track_helicone(agent_type="supervisor")
    async def run_turn(self, turn_context: dict):
        final_prompt = self.turn_prompt.format(
            message_history=turn_context["message_history"],
            current_subject=turn_context["current_subject"],
            generated_question=turn_context["generated_question"],
        )
        logger.info(f"PROMPT SUPERVISOR: {final_prompt}")
        return await self._run(final_prompt, turn_context.get("deps"))

    @track_helicone(agent_type="supervisor")
    async def run_off_topic(self, off_topic_context: dict):
        final_prompt = self.off_topic_prompt.format(
            message_history=off_topic_context["message_history"],
            generated_question=off_topic_context["generated_question"],
            deviation_count=off_topic_context["deviation_count"],
        )
        logger.info(f"PROMPT SUPERVISOR (off topic): {final_prompt}")
        return await self._run(final_prompt, off_topic_context.get("deps"))

    @track_helicone(agent_type="supervisor")
    async def run_retype(self, retype_context: dict):
        final_prompt = self.retype_prompt.format(
            message_history=retype_context["message_history"],
            regenerated_question=retype_context["regenerated_question"],
        )
        return await self._run(final_prompt, retype_context.get("deps"))

    @track_helicone(agent_type="supervisor")
    async def run_close(self, close_context: dict):
        final_prompt = self.close_prompt.format(
            user_name=close_context["user_name"],
            skill_name=close_context["skill_name"],
        )
        return await self._run(final_prompt, close_context.get("deps"))

    @track_helicone(agent_type="supervisor")
    async def run_greeting(self, greeting_context: dict):
        final_prompt = self.greeting_prompt.format(
            skill_name=greeting_context["skill_name"],
            subjects=greeting_context["subjects"],
            user_name=greeting_context["user_name"],
            first_question=greeting_context["first_question"],
        )
        return await self._run(final_prompt, greeting_context.get("deps"))


def _reconhecimento(ctx: RunContext[SupervisorDeps]) -> str:
    """Reconhecimento factual do que a resposta anterior cobriu."""
    if not ctx.deps or not ctx.deps.ponto_forte_anterior:
        return ""
    ponto = ctx.deps.ponto_forte_anterior.strip().rstrip(".")
    return (
        f"Ponto coberto pela resposta anterior: {ponto}. "
        "Reconheça em no máximo meia frase, de forma factual, antes da pergunta. "
        "Nomear o que foi coberto, não elogiar. Nunca resumir a resposta."
    )


def _transicao(ctx: RunContext[SupervisorDeps]) -> str:
    """Orientação de transição quando o assunto muda."""
    if not ctx.deps or not ctx.deps.trocou_de_topico:
        return ""
    return (
        "O assunto mudou. A própria pergunta deve estabelecer o novo contexto. "
        "Não use frase de transição genérica."
    )
