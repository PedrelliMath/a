"""Evidência: a saída única do avaliador.

Observação, jamais decisão (P1). Não existe aqui `classificacao`, `proximo_nivel` nem
`deve_encerrar` — se o agente pudesse devolver qualquer um desses, ele estaria decidindo,
e a progressão deixaria de ser uma função pura da evidência acumulada.

Todo score carrega um trecho literal da resposta (P2). O trecho é verificado em código,
em `app.agents.evaluator.validar_evidencia`: trecho que não existe no texto original
invalida o score.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MotivoNaoResposta = Literal[
    "fora_do_escopo",
    "vazia",
    "skip_solicitado",
    "pedido_de_reformulacao",
]

Confianca = Literal["alta", "media", "baixa"]


class EvidenciaCriterio(BaseModel):
    criterio_id: str
    competencia: str
    score: Literal[0, 1, 2, 3]
    trecho_citado: str | None = Field(
        default=None,
        description="Cópia literal de trecho da resposta. None apenas quando score == 0 por ausência.",
    )
    justificativa: str = Field(default="", max_length=300)


class AntiCriterioDetectado(BaseModel):
    anti_criterio_id: str
    trecho_citado: str


class Evidencia(BaseModel):
    respondeu_a_pergunta: bool
    motivo_nao_resposta: MotivoNaoResposta | None = None
    criterios: list[EvidenciaCriterio] = Field(default_factory=list)
    anti_criterios: list[AntiCriterioDetectado] = Field(default_factory=list)
    gate_por_competencia: dict[str, bool] = Field(default_factory=dict)
    confianca: Confianca = "media"
    ponto_forte: str | None = Field(
        default=None, description="Trecho que o supervisor pode referenciar"
    )
    lacuna: str | None = Field(
        default=None, description="O que faltou, para ancorar a próxima pergunta"
    )

    def competencias_avaliadas(self) -> set[str]:
        return {c.competencia for c in self.criterios} | set(self.gate_por_competencia)
