from sqlalchemy import String, Float, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from app.database.db import Base
from uuid import uuid4, UUID
from datetime import datetime


class HeliconeMetrics(Base):
    """
    Modelo SQLAlchemy para armazenar métricas do Helicone.
    Usado para observabilidade das chamadas de LLM e guardrails (DeepEval).
    """
    __tablename__ = 'helicone_metrics'

    # Identificação
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid4
    )
    
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        primary_key=True,
        nullable=False,
        default=datetime.utcnow
    )
    
    request_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )

    # Agente e modelo
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Tipo do agente: supervisor, message_validator, skill_evaluator, question_generator, guardrails"
    )
    
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Nome do modelo LLM utilizado ou 'deepeval' para guardrails"
    )

    # Performance
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Latência da chamada em milissegundos"
    )

    # Tokens e custos (para LLMs)
    tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="Total de tokens utilizados"
    )
    
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="Tokens do prompt"
    )
    
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="Tokens da resposta"
    )
    
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Custo estimado da chamada em USD"
    )

    # Campos específicos para Guardrails (DeepEval) - preparados para implementação futura
    overall_safety_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score geral de segurança do DeepEval"
    )
    
    violations_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="Número de violações detectadas"
    )
    
    is_safe: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
        comment="Se o conteúdo foi considerado seguro"
    )
    
    bias_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score de viés geral"
    )
    
    toxicity_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score de toxicidade"
    )
    
    hate_speech_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score de discurso de ódio"
    )
    
    religious_bias_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score de viés religioso"
    )
    
    racial_bias_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment="Score de viés racial"
    )
    
    processing_components: Mapped[list] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="Lista de componentes de processamento utilizados"
    )

    # Auditoria
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=True
    )

    def to_dict(self) -> dict:
        """Converte o modelo para dicionário"""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost": self.cost,
            "overall_safety_score": self.overall_safety_score,
            "violations_count": self.violations_count,
            "is_safe": self.is_safe,
            "bias_score": self.bias_score,
            "toxicity_score": self.toxicity_score,
            "hate_speech_score": self.hate_speech_score,
            "religious_bias_score": self.religious_bias_score,
            "racial_bias_score": self.racial_bias_score,
            "processing_components": self.processing_components,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
