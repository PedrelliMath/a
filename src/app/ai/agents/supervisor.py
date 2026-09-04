from dataclasses import dataclass, field

from pydantic_ai import Agent, ModelMessage, RunContext
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.messages import ModelRequest, ToolReturnPart

from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)

# Quantas mensagens do histórico chegam ao modelo em cada run (R8).
# Recência é só uma das camadas de memória: cobertura e âncoras entram por
# instructions dinâmicas e não dependem da janela.
HISTORY_MESSAGE_LIMIT = 8


@dataclass
class SupervisorDeps:
    """Contexto do turno usado pelas instructions dinâmicas do supervisor."""

    topico_atual: str = ""
    ponto_forte_anterior: str | None = None
    trocou_de_topico: bool = False
    topicos_cobertos: list[str] = field(default_factory=list)
    ancoras: list[tuple[str, str]] = field(default_factory=list)


def ultimas_trocas(messages: list[ModelMessage]) -> list[ModelMessage]:
    """
    Camada de continuidade: só as últimas trocas vão ao modelo.

    O supervisor responde em texto puro e não usa ferramentas, então não há
    par de tool call para quebrar. A guarda abaixo existe para o caso de o
    agente voltar a ter saída estruturada: um retorno de ferramenta sem a
    chamada correspondente é rejeitado pelo provedor.
    """
    if len(messages) <= HISTORY_MESSAGE_LIMIT:
        return messages

    window = messages[-HISTORY_MESSAGE_LIMIT:]
    while window and _starts_with_tool_return(window[0]):
        window = window[1:]

    return window


def _starts_with_tool_return(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and isinstance(
        message.parts[0], ToolReturnPart
    )


class AgentSupervisor:
    """
    Supervisor da conversa.

    O prompt persistente (identidade, postura, formato, limites) é registrado
    como `instructions`, e não como `system_prompt`. Instructions são
    reaplicadas em toda run, inclusive quando há `message_history`, então as
    regras de conduta valem em todos os caminhos (greeting, turno, desvio,
    retype e close) e não só no turno normal.

    O histórico chega como `message_history` (turnos com papéis de verdade) e é
    cortado pela capability `ProcessHistory`. A saída é texto puro justamente
    para que o histórico não carregue pares de tool call: sem eles, fatiar o
    histórico é seguro e as mensagens anteriores do supervisor aparecem como
    texto de assistente, não como argumento de ferramenta.
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
            output_type=str,
            instructions=system_prompt,
            capabilities=[ProcessHistory(ultimas_trocas)],
        )

        self.runner.instructions(_reconhecimento)
        self.runner.instructions(_transicao)
        self.runner.instructions(_cobertura)
        self.runner.instructions(_ancoras)

    async def _run(self, prompt: str, context: dict):
        return await self.runner.run(
            user_prompt=prompt,
            deps=context.get("deps") or SupervisorDeps(),
            message_history=context.get("message_history") or None,
        )

    @track_helicone(agent_type="supervisor")
    async def run_turn(self, turn_context: dict):
        final_prompt = self.turn_prompt.format(
            current_subject=turn_context["current_subject"],
            generated_question=turn_context["generated_question"],
        )
        logger.info(f"PROMPT SUPERVISOR: {final_prompt}")
        return await self._run(final_prompt, turn_context)

    @track_helicone(agent_type="supervisor")
    async def run_off_topic(self, off_topic_context: dict):
        final_prompt = self.off_topic_prompt.format(
            generated_question=off_topic_context["generated_question"],
            deviation_count=off_topic_context["deviation_count"],
        )
        logger.info(f"PROMPT SUPERVISOR (off topic): {final_prompt}")
        return await self._run(final_prompt, off_topic_context)

    @track_helicone(agent_type="supervisor")
    async def run_retype(self, retype_context: dict):
        final_prompt = self.retype_prompt.format(
            regenerated_question=retype_context["regenerated_question"],
        )
        return await self._run(final_prompt, retype_context)

    @track_helicone(agent_type="supervisor")
    async def run_close(self, close_context: dict):
        final_prompt = self.close_prompt.format(
            user_name=close_context["user_name"],
            skill_name=close_context["skill_name"],
        )
        return await self._run(final_prompt, close_context)

    @track_helicone(agent_type="supervisor")
    async def run_greeting(self, greeting_context: dict):
        final_prompt = self.greeting_prompt.format(
            skill_name=greeting_context["skill_name"],
            subjects=greeting_context["subjects"],
            user_name=greeting_context["user_name"],
            first_question=greeting_context["first_question"],
        )
        return await self._run(final_prompt, greeting_context)


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


def _cobertura(ctx: RunContext[SupervisorDeps]) -> str:
    """Camada de cobertura: o que já foi perguntado nesta sessão."""
    if not ctx.deps or not ctx.deps.topicos_cobertos:
        return ""
    return "Tópicos já cobertos, não repita: " + ", ".join(ctx.deps.topicos_cobertos)


def _ancoras(ctx: RunContext[SupervisorDeps]) -> str:
    """Camada de âncoras: trechos literais ditos pelo candidato."""
    if not ctx.deps or not ctx.deps.ancoras:
        return ""
    linhas = "\n".join(f'- sobre {t}: "{trecho}"' for t, trecho in ctx.deps.ancoras)
    return f"O candidato disse antes:\n{linhas}\nVocê pode referenciar isso."
