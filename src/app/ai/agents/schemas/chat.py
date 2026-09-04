from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.logger import get_log
from app.models.session import Session

logger = get_log(__name__)


def deserialize_model_messages(blob: list | None) -> list[ModelMessage]:
    """Converte o JSON gravado em `sessions.model_messages` de volta em mensagens."""
    if not blob:
        return []
    try:
        return ModelMessagesTypeAdapter.validate_python(blob)
    except Exception as exc:  # formato antigo ou corrompido: não derruba a sessão
        logger.warning(f"Não foi possível ler model_messages da sessão: {exc}")
        return []


def transcript_to_model_messages(message_history: list[dict]) -> list[ModelMessage]:
    """
    Deriva um histórico em `ModelMessage` a partir das mensagens gravadas.

    Usado para sessões criadas antes da coluna `model_messages` existir: elas
    entram no formato novo sem perder a conversa.
    """
    messages: list[ModelMessage] = []
    for msg in message_history:
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        if msg.get("user_type") == "bot":
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
        else:
            messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))

    return messages


@dataclass(frozen=True)
class ChatContextIn():
    """Dados necessários antes de iniciar o orquestrador"""
    session: Session
    ai_message: str
    user_response: str
    current_proficiency_level: str
    current_question_set: str
    current_specific_skill: str
    message_history: list[dict]
    rubrics: dict
    bloom_levels: dict
    model_messages: list[ModelMessage] = field(default_factory=list)

    def get_message_history(self, num_messages: int | None = None):
        if num_messages is not None and num_messages <= len(self.message_history):
            messages = self.message_history[-num_messages:]
        else:
            messages = self.message_history

        return "\n".join(
            f'\n{msg["user_type"]}: {msg["text"]}'
            for msg in messages
        )

    def supervisor_history(self, user_message: str | None = None) -> list[ModelMessage]:
        """
        Histórico que vai ao supervisor como `message_history`.

        Sessões novas leem a coluna `model_messages`; sessões antigas derivam o
        histórico do transcript. No primeiro caso a resposta atual do candidato
        ainda não está no blob e precisa ser anexada; no segundo ela já está.
        """
        if self.model_messages:
            history = list(self.model_messages)
            if user_message:
                history.append(
                    ModelRequest(parts=[UserPromptPart(content=user_message)])
                )
            return history

        return transcript_to_model_messages(self.message_history)


@dataclass(frozen=True)
class ChatContextOut():
    """Dados de saída após a execução do orquestrador"""
    supervisor_message: str | None = None
    params: dict | None = None
    pre_messages: list[dict] | None = None
    model_messages: list[Any] | None = None


@dataclass
class ChatContextRunning():
    "Dados que podem ser alterados durante a execução do chat"
    new_proficiency_level: str | None = None
    new_specific_skill: str | None = None
