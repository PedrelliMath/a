from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.helicone_metrics import HeliconeMetrics
from app.logger import get_log

logger = get_log(__name__)


class HeliconeMetricsRepository:
    """Repositório para persistir métricas do Helicone no PostgreSQL"""

    def __init__(self, db: DBSession):
        self.db = db

    def create(self, metrics_data: dict) -> HeliconeMetrics:
        """
        Cria um novo registro de métricas.
        
        Args:
            metrics_data: Dicionário com os dados das métricas
            
        Returns:
            HeliconeMetrics: Registro criado
        """
        try:
            metrics = HeliconeMetrics(**metrics_data)
            self.db.add(metrics)
            self.db.commit()
            self.db.refresh(metrics)
            logger.info(f"Métricas salvas com sucesso: {metrics.id}")
            return metrics
        except Exception as e:
            logger.error(f"Erro ao salvar métricas: {e}")
            self.db.rollback()
            raise

    def create_async_safe(self, metrics_data: dict) -> Optional[HeliconeMetrics]:
        """
        Cria um registro de forma segura (não propaga exceções).
        Útil para não interromper o fluxo principal em caso de erro.
        
        Args:
            metrics_data: Dicionário com os dados das métricas
            
        Returns:
            HeliconeMetrics ou None em caso de erro
        """
        try:
            return self.create(metrics_data)
        except Exception as e:
            logger.warning(f"Falha ao salvar métricas (não crítico): {e}")
            return None

    def get_by_id(self, metrics_id: UUID, timestamp: datetime) -> Optional[HeliconeMetrics]:
        """
        Busca métricas por ID e timestamp (chave composta).
        
        Args:
            metrics_id: UUID do registro
            timestamp: Timestamp do registro
            
        Returns:
            HeliconeMetrics ou None
        """
        return self.db.query(HeliconeMetrics).filter(
            HeliconeMetrics.id == metrics_id,
            HeliconeMetrics.timestamp == timestamp
        ).first()

    def get_by_session_id(self, session_id: str) -> List[HeliconeMetrics]:
        """
        Busca todas as métricas de uma sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Lista de HeliconeMetrics
        """
        return self.db.query(HeliconeMetrics).filter(
            HeliconeMetrics.session_id == session_id
        ).order_by(HeliconeMetrics.timestamp.desc()).all()

    def get_by_user_id(self, user_id: str) -> List[HeliconeMetrics]:
        """
        Busca todas as métricas de um usuário.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Lista de HeliconeMetrics
        """
        return self.db.query(HeliconeMetrics).filter(
            HeliconeMetrics.user_id == user_id
        ).order_by(HeliconeMetrics.timestamp.desc()).all()

    def get_by_agent_type(self, agent_type: str, limit: int = 100) -> List[HeliconeMetrics]:
        """
        Busca métricas por tipo de agente.
        
        Args:
            agent_type: Tipo do agente
            limit: Limite de registros
            
        Returns:
            Lista de HeliconeMetrics
        """
        return self.db.query(HeliconeMetrics).filter(
            HeliconeMetrics.agent_type == agent_type
        ).order_by(HeliconeMetrics.timestamp.desc()).limit(limit).all()

    def get_recent(self, limit: int = 100) -> List[HeliconeMetrics]:
        """
        Busca as métricas mais recentes.
        
        Args:
            limit: Limite de registros
            
        Returns:
            Lista de HeliconeMetrics
        """
        return self.db.query(HeliconeMetrics).order_by(
            HeliconeMetrics.timestamp.desc()
        ).limit(limit).all()

    def get_stats_by_agent_type(self, agent_type: str) -> dict:
        """
        Retorna estatísticas agregadas para um tipo de agente.
        Útil para dashboards.
        
        Args:
            agent_type: Tipo do agente
            
        Returns:
            Dict com estatísticas (avg_latency, total_tokens, total_cost, count)
        """
        from sqlalchemy import func
        
        result = self.db.query(
            func.count(HeliconeMetrics.id).label('count'),
            func.avg(HeliconeMetrics.latency_ms).label('avg_latency'),
            func.sum(HeliconeMetrics.tokens).label('total_tokens'),
            func.sum(HeliconeMetrics.cost).label('total_cost')
        ).filter(
            HeliconeMetrics.agent_type == agent_type
        ).first()
        
        return {
            "agent_type": agent_type,
            "count": result.count or 0,
            "avg_latency_ms": float(result.avg_latency) if result.avg_latency else 0.0,
            "total_tokens": result.total_tokens or 0,
            "total_cost": float(result.total_cost) if result.total_cost else 0.0
        }
