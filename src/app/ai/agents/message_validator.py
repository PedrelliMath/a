from pydantic import BaseModel, Field
from pydantic_ai import Agent
from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)

from typing import List, Optional, Literal


class FollowupInstruction(BaseModel):
    intent: Literal[
        "aprofundar",
        "clarificar",
        "completar_resposta",
        "pedir_exemplo",
    ] = Field(
        ...,
        description="Tipo de ação que a próxima pergunta deve executar.",
    )
    focus: str = Field(
        ...,
        description="Elemento específico que falta na resposta (ex: 'exemplo prático', 'detalhamento do processo').",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Regras que a pergunta deve seguir (ex: 'ser objetiva').",
    )


class AgentMessageValidatorResponse(BaseModel):
    is_valid: bool = Field(
        ...,
        description="True se a resposta é válida para avaliação ou complementação.",
    )
    reason: Literal["valid", "incomplete", "invalid"] = Field(
        ...,
        description="""
        Classificação da resposta:
        - valid: resposta completa e adequada
        - incomplete: resposta parcialmente correta, precisa de complemento
        - invalid: resposta irrelevante, vaga ou fora do contexto
        """,
    )
    explicacao: Optional[str] = Field(
        default=None,
        description="""
        Justificativa objetiva explicando o motivo da classificação.
        Obrigatória quando reason != 'valid'.
        """,
    )
    missing_parts: List[str] = Field(
        default_factory=list,
        description="""
        Lista específica do que está faltando na resposta.
        Obrigatório quando reason = 'incomplete'.
        """,
    )
    followup_instruction: Optional[FollowupInstruction] = Field(
        default=None,
        description="""
        Instruções estruturadas para gerar a próxima pergunta.
        Deve ser preenchido apenas quando reason = 'incomplete'.
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
            message_history=validation_context['message_history'],
            question=validation_context['question'],
            answer=validation_context['user_message'],
            invalid_history=validation_context.get("invalid_history", "Nenhuma tentativa inválida anterior."),
        )
        logger.info(f"run_validation final_prompt:\n{final_prompt}")
        result = await self.runner.run(user_prompt=final_prompt)
        return result