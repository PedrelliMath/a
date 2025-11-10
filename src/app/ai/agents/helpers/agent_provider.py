from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.config import settings


class AgentProvider:
    def __init__(self, provider: str, model: str, api_key: str):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def get_agent_provider(self):
        match self.provider:
            case "openrouter":
                return OpenAIChatModel(
                    self.model, provider=OpenRouterProvider(api_key=self.api_key)
                )
            case "openai":
                return OpenAIChatModel(
                    self.model,
                    provider=OpenAIProvider(
                        api_key=self.api_key, base_url=settings.OPENAI_BASE_URL
                    ),
                )

            case _:
                raise Exception("No valid provider selected")
