"""
Decorator para tracking de métricas Helicone nos agentes de IA.
Implementa o padrão Aspect/Decorator para não poluir o código dos agentes.
"""
import time
import functools
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from contextvars import ContextVar

from app.logger import get_log
from app.database.db import SessionLocal
from app.repository.helicone_metrics import HeliconeMetricsRepository
from .helicone_client import helicone_client

logger = get_log(__name__)

# Context variable para passar informações da sessão entre chamadas
_helicone_context: ContextVar[Optional['HeliconeContext']] = ContextVar(
    'helicone_context', 
    default=None
)


@dataclass
class HeliconeContext:
    """
    Contexto para tracking do Helicone.
    Armazena informações da sessão atual para as métricas.
    """
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    extra_metadata: dict = field(default_factory=dict)
    
    def __enter__(self):
        self._token = _helicone_context.set(self)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _helicone_context.reset(self._token)
        return False


def get_current_context() -> Optional[HeliconeContext]:
    """Retorna o contexto Helicone atual"""
    return _helicone_context.get()


def set_helicone_context(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **extra_metadata
) -> HeliconeContext:
    """
    Cria e define um novo contexto Helicone.
    
    Args:
        session_id: ID da sessão
        user_id: ID do usuário
        **extra_metadata: Metadados adicionais
        
    Returns:
        HeliconeContext configurado
    """
    context = HeliconeContext(
        session_id=session_id,
        user_id=user_id,
        extra_metadata=extra_metadata
    )
    _helicone_context.set(context)
    return context


def track_helicone(
    agent_type: str,
    save_metrics: bool = True
) -> Callable:
    """
    Decorator para tracking de métricas Helicone.
    
    Captura automaticamente:
    - Latência da chamada
    - Tokens utilizados (do resultado do pydantic-ai)
    - Custo estimado
    - Informações do contexto (session_id, user_id)
    
    Args:
        agent_type: Tipo do agente (supervisor, message_validator, etc.)
        save_metrics: Se True, salva métricas no PostgreSQL
        
    Returns:
        Decorator function
        
    Exemplo de uso:
        @track_helicone(agent_type="message_validator")
        async def run_validation(self, validation_context: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Verificar se tracking está habilitado
            if not helicone_client.is_enabled:
                return await func(*args, **kwargs)
            
            # Capturar tempo inicial
            start_time = time.perf_counter()
            result = None
            error = None
            
            try:
                # Executar função original
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                error = e
                raise
                
            finally:
                # Calcular latência
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                # Obter contexto atual
                context = get_current_context()
                session_id = context.session_id if context else None
                user_id = context.user_id if context else None
                
                # Tentar extrair informações do agente
                agent = None
                if args and hasattr(args[0], 'runner'):
                    agent = args[0].runner
                
                model = helicone_client.extract_model_from_agent(agent) if agent else "unknown"
                
                # Extrair usage do resultado
                usage = {"prompt_tokens": None, "completion_tokens": None}
                if result is not None:
                    usage = helicone_client.extract_usage_from_result(result)
                
                # Construir dados das métricas
                metrics_data = helicone_client.build_metrics_data(
                    agent_type=agent_type,
                    model=model,
                    latency_ms=latency_ms,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    session_id=session_id,
                    user_id=user_id,
                )
                
                # Log para debug
                logger.debug(
                    f"Helicone tracking - Agent: {agent_type}, "
                    f"Model: {model}, Latency: {latency_ms:.2f}ms, "
                    f"Tokens: {usage.get('prompt_tokens', '?')}/{usage.get('completion_tokens', '?')}"
                )
                
                # Salvar métricas no banco (de forma não-bloqueante)
                if save_metrics:
                    _save_metrics_async(metrics_data)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Versão síncrona (menos comum para agentes de IA)
            if not helicone_client.is_enabled:
                return func(*args, **kwargs)
            
            start_time = time.perf_counter()
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                context = get_current_context()
                metrics_data = helicone_client.build_metrics_data(
                    agent_type=agent_type,
                    model="unknown",
                    latency_ms=latency_ms,
                    session_id=context.session_id if context else None,
                    user_id=context.user_id if context else None,
                )
                
                if save_metrics:
                    _save_metrics_async(metrics_data)
        
        # Retornar wrapper apropriado baseado no tipo da função
        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def _save_metrics_async(metrics_data: dict) -> None:
    """
    Salva métricas no banco de forma segura (não propaga erros).
    
    Args:
        metrics_data: Dados das métricas para salvar
    """
    try:
        db = SessionLocal()
        try:
            repo = HeliconeMetricsRepository(db)
            repo.create_async_safe(metrics_data)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Falha ao salvar métricas Helicone (não crítico): {e}")


def asyncio_iscoroutinefunction(func: Callable) -> bool:
    """Verifica se a função é uma coroutine"""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# Decorator alternativo usando classe (para casos mais complexos)
class HeliconeTracker:
    """
    Classe alternativa para tracking que permite configuração mais granular.
    
    Exemplo de uso:
        tracker = HeliconeTracker(agent_type="supervisor")
        
        with tracker.track():
            result = await agent.run(...)
    """
    
    def __init__(
        self, 
        agent_type: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.agent_type = agent_type
        self.session_id = session_id
        self.user_id = user_id
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        return False
    
    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        return False
    
    @property
    def latency_ms(self) -> Optional[float]:
        """Retorna a latência em milissegundos"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    def save_metrics(
        self, 
        model: str = "unknown",
        result: Any = None,
        **extra_fields
    ) -> None:
        """
        Salva as métricas coletadas.
        
        Args:
            model: Nome do modelo
            result: Resultado do agente (para extrair usage)
            **extra_fields: Campos adicionais
        """
        if not helicone_client.is_enabled:
            return
        
        usage = helicone_client.extract_usage_from_result(result) if result else {}
        
        metrics_data = helicone_client.build_metrics_data(
            agent_type=self.agent_type,
            model=model,
            latency_ms=self.latency_ms or 0,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            session_id=self.session_id,
            user_id=self.user_id,
            **extra_fields
        )
        
        _save_metrics_async(metrics_data)
