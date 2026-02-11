"""
Cliente Helicone para configurar proxy e processar métricas.
"""
from typing import Optional, Dict, Any
from uuid import uuid4, UUID
from datetime import datetime

from app.logger import get_log
from app.config import settings

logger = get_log(__name__)


# Tabela de custos por modelo (USD por 1K tokens) - valores aproximados
MODEL_COSTS = {
    # OpenAI GPT-4
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    # OpenAI GPT-3.5
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
    # Default fallback
    "default": {"prompt": 0.001, "completion": 0.002},
}


class HeliconeClient:
    """
    Cliente para gerenciar integração com Helicone.
    Processa métricas e prepara dados para persistência.
    """
    
    def __init__(self):
        self.enabled = settings.helicone_enabled
        self._api_key = settings.helicone_api_key
        self.base_url = settings.helicone_base_url
        
        if self.enabled and not self._api_key:
            logger.warning(
                "Helicone está habilitado mas HELICONE_API_KEY não está configurada. "
                "Métricas serão coletadas localmente mas não enviadas ao Helicone."
            )
    
    @property
    def api_key(self) -> Optional[str]:
        """Retorna a API key do Helicone"""
        if self._api_key:
            return self._api_key.get_secret_value()
        return None
    
    @property
    def is_enabled(self) -> bool:
        """Verifica se o tracking está habilitado"""
        return self.enabled
    
    def get_helicone_headers(self, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Retorna os headers necessários para o proxy Helicone.
        
        Args:
            metadata: Metadados adicionais para incluir nos headers
            
        Returns:
            Dict com headers do Helicone
        """
        if not self.api_key:
            return {}
        
        headers = {
            "Helicone-Auth": f"Bearer {self.api_key}",
        }
        
        if metadata:
            if "session_id" in metadata:
                headers["Helicone-Session-Id"] = str(metadata["session_id"])
            if "user_id" in metadata:
                headers["Helicone-User-Id"] = str(metadata["user_id"])
            if "agent_type" in metadata:
                headers["Helicone-Property-Agent-Type"] = metadata["agent_type"]
        
        return headers
    
    def get_helicone_base_url(self) -> str:
        """Retorna a URL base do proxy Helicone para OpenAI"""
        return self.base_url
    
    def calculate_cost(
        self, 
        model: str, 
        prompt_tokens: int, 
        completion_tokens: int
    ) -> float:
        """
        Calcula o custo estimado de uma chamada.
        
        Args:
            model: Nome do modelo
            prompt_tokens: Tokens do prompt
            completion_tokens: Tokens da resposta
            
        Returns:
            Custo estimado em USD
        """
        # Normalizar nome do modelo
        model_lower = model.lower()
        
        # Buscar custo do modelo ou usar default
        costs = MODEL_COSTS.get(model_lower, MODEL_COSTS["default"])
        
        prompt_cost = (prompt_tokens / 1000) * costs["prompt"]
        completion_cost = (completion_tokens / 1000) * costs["completion"]
        
        return round(prompt_cost + completion_cost, 6)
    
    def build_metrics_data(
        self,
        agent_type: str,
        model: str,
        latency_ms: float,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Constrói o dicionário de dados para persistir no banco.
        
        Args:
            agent_type: Tipo do agente
            model: Nome do modelo
            latency_ms: Latência em milissegundos
            prompt_tokens: Tokens do prompt
            completion_tokens: Tokens da resposta
            session_id: ID da sessão
            user_id: ID do usuário
            request_id: ID da requisição
            **extra_fields: Campos adicionais (para guardrails/DeepEval)
            
        Returns:
            Dict pronto para criar HeliconeMetrics
        """
        # Calcular totais
        tokens = None
        cost = None
        
        if prompt_tokens is not None and completion_tokens is not None:
            tokens = prompt_tokens + completion_tokens
            cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        
        metrics_data = {
            "id": uuid4(),
            "timestamp": datetime.utcnow(),
            "request_id": request_id or str(uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type,
            "model": model,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        }
        
        # Adicionar campos extras (guardrails)
        guardrail_fields = [
            "overall_safety_score",
            "violations_count", 
            "is_safe",
            "bias_score",
            "toxicity_score",
            "hate_speech_score",
            "religious_bias_score",
            "racial_bias_score",
            "processing_components"
        ]
        
        for field in guardrail_fields:
            if field in extra_fields:
                metrics_data[field] = extra_fields[field]
        
        return metrics_data
    
    def extract_usage_from_result(self, result: Any) -> Dict[str, Optional[int]]:
        """
        Extrai informações de uso (tokens) do resultado do pydantic-ai.
        
        Args:
            result: Resultado do Agent.run()
            
        Returns:
            Dict com prompt_tokens e completion_tokens
        """
        usage_dict = {
            "prompt_tokens": None,
            "completion_tokens": None
        }
        
        try:
            # pydantic-ai retorna usage como um metodo que precisa ser chamado
            if hasattr(result, 'usage') and callable(result.usage):
                usage_obj = result.usage()
                
                # pydantic-ai usa request_tokens e response_tokens
                if hasattr(usage_obj, 'request_tokens'):
                    usage_dict["prompt_tokens"] = usage_obj.request_tokens
                if hasattr(usage_obj, 'response_tokens'):
                    usage_dict["completion_tokens"] = usage_obj.response_tokens
                
                logger.debug(
                    f"Usage extraído: prompt={usage_dict['prompt_tokens']}, "
                    f"completion={usage_dict['completion_tokens']}"
                )
            else:
                logger.debug("result.usage não encontrado ou não é callable")
                    
        except Exception as e:
            logger.warning(f"Erro ao extrair usage do resultado: {e}", exc_info=True)
        
        return usage_dict
    
    def extract_model_from_agent(self, agent: Any) -> str:
        """
        Extrai o nome do modelo do agente pydantic-ai.
        
        Args:
            agent: Instância do Agent
            
        Returns:
            Nome do modelo ou 'unknown'
        """
        try:
            if hasattr(agent, 'model'):
                model = agent.model
                if isinstance(model, str):
                    # Remove prefixo "openai:" se presente
                    if model.startswith("openai:"):
                        return model[7:]
                    return model
                elif hasattr(model, 'name'):
                    return model.name
                elif hasattr(model, 'model_name'):
                    return model.model_name
        except Exception as e:
            logger.debug(f"Não foi possível extrair modelo do agente: {e}")
        
        return "unknown"


# Instância singleton
helicone_client = HeliconeClient()
