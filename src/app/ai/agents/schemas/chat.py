from dataclasses import dataclass
from app.models.session import Session

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

    def get_message_history(self, num_messages: int | None = None):
        if num_messages is not None and num_messages <= len(self.message_history):
            messages = self.message_history[:num_messages]
        else:
            messages = self.message_history

        return "\n".join(
            f'\n{msg["user_type"]}: {msg["text"]}'
            for msg in messages
        )

@dataclass(frozen=True)
class ChatContextOut():
    """Dados de saída após a execução do orquestrador"""
    supervisor_message: str | None = None
    params: dict | None = None
    pre_messages: list[dict] | None = None


@dataclass
class ChatContextRunning():
    "Dados que podem ser alterados durante a execução do chat"
    new_proficiency_level: str | None = None
    new_specific_skill: str | None = None
    