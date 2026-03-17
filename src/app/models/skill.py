from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, text, func, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.db import Base
from uuid import uuid4, UUID
from datetime import datetime
from typing import List, TypedDict

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session
    from .evaluation import Evaluation

example_questions_dict = {
    "rubrics": {
        "Dados e Inteligência Artificial, Orientação a Serviços e ao Cliente, Solução de Problemas": {
          "lembrar": [
            "Qual foi a última vez que você identificou um problema recorrente e como reconheceu o padrão?",
            "Como seu trabalho influencia a experiência do cliente, interna ou externa?",
            "Quais dados você costuma acompanhar e o que eles indicam?"
          ],
          "compreender": [
            "Como você explicaria a causa de um problema recorrente no seu time?",
            "Por que a estruturação de dados é importante para tomar boas decisões?"
          ],
          "aplicar": [
            "Que metodologia você usou para resolver um problema real com o time?",
            "Como você já usou dados para tomar uma decisão importante?"
          ],
          "analisar": [
            "Como você dividiu um problema complexo para entender melhor suas partes?",
            "Como você transforma dados em insights práticos?"
          ],
          "avaliar": [
            "Como você avaliou diferentes soluções para um problema estratégico?",
            "Como você valida se uma decisão baseada em dados deu resultado?"
          ],
          "criar": [
            "Qual foi a solução mais inovadora que você já criou para um desafio relevante?",
            "Você já criou alguma solução baseada em dados ou IA? Como foi?"
          ]
        },
        "Conhecimento de Negócio, Curiosidade, Fluência Digital, Visão de Longo Prazo": {
          "lembrar": [
            "Quais tendências você acompanha e por quê?",
            "Quais ferramentas digitais você usa para facilitar seu trabalho?",
            "Quais são os blocos essenciais de um modelo de negócio que você conhece?"
          ],
          "compreender": [
            "Como você conecta uma tendência de mercado à estratégia da empresa?",
            "Como suas decisões influenciam receita, custo ou margem?"
          ],
          "aplicar": [
            "Você já tomou uma decisão baseada em uma visão de longo prazo? Como?",
            "Que decisão recente você tomou com base em análise de negócio?"
          ],
          "analisar": [
            "Como você antecipa possíveis rupturas no seu setor?",
            "Como você avalia se a operação está alinhada com a estratégia de negócio?"
          ],
          "avaliar": [
            "Como você avalia se uma estratégia futura é viável?",
            "Como você avalia se uma oportunidade de negócio vale o investimento?"
          ],
          "criar": [
            "Que modelo você já ajudou a criar pensando em sustentabilidade futura?",
            "Que tipo de plano ou modelo de negócio você já ajudou a criar?"
          ]
        },
        "Colaboração, Empatia": {
          "lembrar": [
            "Quais práticas você considera essenciais para uma comunicação eficaz?",
            "Como você percebe que alguém está desconfortável numa conversa?"
          ],
          "compreender": [
            "Como estilos diferentes de liderança influenciam a colaboração em equipe?",
            "Como você explica o papel da empatia no trabalho em equipe?"
          ],
          "aplicar": [
            "Como você contribuiu para melhorar a colaboração no seu time?",
            "Como você usa a empatia para dar feedback ou resolver conflitos?"
          ],
          "analisar": [
            "Quais padrões você já identificou que dificultavam a colaboração?",
            "Você já mapeou comportamentos prejudiciais dentro de um time? Como?"
          ],
          "avaliar": [
            "Como você mede se a colaboração está dando certo?",
            "Como você percebe se a empatia está contribuindo para o clima organizacional?"
          ],
          "criar": [
            "Você já criou alguma estrutura para fortalecer colaboração entre áreas?",
            "Que iniciativas você já criou para promover inclusão e escuta ativa?"
          ]
        },
        "Autoconhecimento": {
          "lembrar": [
            "Quais comportamentos você percebe que se repetem em situações de pressão?"
          ],
          "compreender": [
            "Como você descreveria seu estilo de trabalho e seu impacto no time?"
          ],
          "aplicar": [
            "Quais hábitos você cultiva para manter foco e organização?"
          ],
          "analisar": [
            "Como você percebe desalinhamentos entre o que acredita e como age?"
          ],
          "avaliar": [
            "Como você revisa e adapta seus objetivos pessoais e profissionais?"
          ],
          "criar": [
            "Que estratégias você usa para construir sua identidade profissional?"
          ]
        }
    },
    "bloom_levels":{
        "lembrar": {
            "descricao":"Capacidade de recordar fatos, conceitos e informações básicas aprendidas anteriormente. Envolve identificar, listar, nomear ou reconhecer informações sem a necessidade de interpretação ou aplicação.",
            "acima": "compreender",
            "abaixo": "lembrar"
        },
        "compreender": {
            "descricao":"Capacidade de explicar ideias ou conceitos com base na compreensão de seu significado. Inclui resumir, interpretar, comparar e exemplificar informações adquiridas.",
            "acima": "aplicar",
            "abaixo": "lembrar"
        },
        "aplicar": {
            "descricao":"Capacidade de usar o conhecimento adquirido em situações reais. Envolve implementar conceitos, técnicas ou habilidades em contextos práticos de trabalho.",
            "acima": "analisar",
            "abaixo": "compreender"
        },
        "analisar": {
            "descricao":"Capacidade de dividir informações em partes e entender suas inter-relações. Envolve examinar, categorizar, detectar padrões e identificar causas ou consequências.",
            "acima": "avaliar",
            "abaixo": "aplicar"
        },
        "avaliar": {
            "descricao":"Capacidade de fazer julgamentos fundamentados com base em critérios definidos. Inclui analisar alternativas, justificar escolhas e medir resultados.",
            "acima": "criar",
            "abaixo": "analisar"
        },
        "criar": {
            "descricao":"Capacidade de gerar novas ideias, produtos ou processos. Envolve planejar, produzir e desenvolver soluções originais a partir de conhecimentos diversos.",
            "acima": "criar",
            "abaixo": "avaliar"
        }
    }
}

model_config_dict = {
    "supervisor":{
        "model_name":"gpt-4o-mini",
        "temperature":0.3,
        "max_tokens":1000
    },
    "question_generator":{
        "model_name":"gpt-4o-mini",
        "temperature":0.3,
        "max_tokens":1000
    },
    "question_regenerator":{
        "model_name":"gpt-4o-mini",
        "temperature":0.3,
        "max_tokens":1000
    },
    "skill_evaluator":{
        "model_name":"ft:gpt-4.1-mini-2025-04-14:projeto-koru:bloom-evaluator:DK4dkBG2",
        "temperature":0.0,
        "max_tokens":1000
    }
}

class SkillInput(BaseModel):
    """Schema de entrada para criar/atualizar skill"""
    name: str = Field(examples=["Liderença"])
    description: str = Field(examples=["Avaliar liderança"])
    questions: dict = Field(
        examples=[example_questions_dict]
    )
    agents_config: dict = Field(
        examples=[model_config_dict]
    )

class SkillOutput(BaseModel):
    """Schema de saída para skill"""
    id: str
    name: str
    description: str
    questions: dict = Field(
        examples=[example_questions_dict]
    )
    agents_config: dict = Field(
        examples=[model_config_dict]
    )
    active: bool
    created_at: datetime
    updated_at: datetime

class Skill(Base):
    """Modelo SQLAlchemy para Skills"""
    __tablename__ = 'skills'

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        unique=True, 
        nullable=False,
        default=uuid4
    )

    name: Mapped[str] = mapped_column(
        String(155),
        unique=True,
        nullable=False,
        index=True
    )

    description: Mapped[str]

    active: Mapped[bool] = mapped_column(
        Boolean(),
        default=True
    )

    questions: Mapped[dict] = mapped_column(
        JSONB, 
        server_default=text("'{}'::jsonb"),
        nullable=False
    )

    agents_config: Mapped[dict] = mapped_column(
        JSONB, 
        server_default=text("'{}'::jsonb"),
        nullable=False
    )

    created_by: Mapped[str] = mapped_column(
        String(36), 
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    sessions: Mapped['Session'] = relationship(back_populates='skill')
    evaluations: Mapped['Evaluation'] = relationship(back_populates='skill')

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name, 
            "description": self.description,
            "questions": self.questions,
            "agents_config": self.agents_config,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_output(self):
        return SkillOutput(
            **self.to_dict()
        )
