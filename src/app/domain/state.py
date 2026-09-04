"""Estado da sessão: a única fonte de verdade (P3).

Proibido derivar estado varrendo mensagens. No v1 o nível corrente e o bloco corrente eram
reconstruídos a cada turno lendo `params` da última mensagem do bot, o que tornava o estado
uma função do histórico de conversa — frágil, não auditável e impossível de reprocessar.

`AssessmentState` é serializado inteiro em JSONB e é a única coisa necessária para retomar
uma sessão.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.domain.bloom import BloomLevel
from app.domain.evidence import Evidencia
from app.domain.items import Item

MotivoConclusaoBloco = Literal[
    "evidencia_concordante",
    "teto_de_itens",
    "anti_criterio_fatal",
    "banco_esgotado",
]


class TurnoRegistro(BaseModel):
    """Uma resposta avaliada. Imutável.

    É o log de auditoria e a base do reprocessamento: dado o histórico de TurnoRegistro,
    o resultado é recomputável em código puro, sem chamar LLM (P5).
    """

    turno: int
    item_id: str
    item_versao: int
    bloco: str
    bloom: BloomLevel
    enunciado_apresentado: str
    mensagem_do_supervisor: str = ""
    resposta_do_candidato: str
    evidencia: Evidencia
    nivel_observado: dict[str, BloomLevel] = Field(default_factory=dict)
    pontuou: bool = Field(description="False para aquecimento e desvios")
    timestamp: datetime


class EstadoCompetencia(BaseModel):
    """Estimativa por competência individual.

    Guardar o nível por competência é o que o v1 descartava: o avaliador já produzia o dado
    e a votação por maioria o colapsava num int de -1 a 1.
    """

    competencia: str
    observacoes: list[BloomLevel] = Field(default_factory=list)
    nivel_estimado: BloomLevel | None = None
    concordante: bool = Field(default=False, description="as duas últimas observações batem")
    theta: float | None = Field(default=None, description="preenchido só na calibração (Fase 7)")
    erro_padrao: float | None = None


class EstadoBloco(BaseModel):
    bloco: str
    bloom_corrente: BloomLevel = BloomLevel.APLICAR
    itens_aplicados: list[str] = Field(default_factory=list)
    turnos_pontuados: int = 0
    concluido: bool = False
    motivo_conclusao: MotivoConclusaoBloco | None = None


class AssessmentState(BaseModel):
    sessao_id: UUID
    skill_id: UUID
    candidato_id: str
    ordem_dos_blocos: list[str] = Field(
        default_factory=list,
        description="Ordem sorteada por sessão, com seed determinística. Ver §6.1.",
    )
    bloco_corrente: str
    blocos: dict[str, EstadoBloco] = Field(default_factory=dict)
    competencias: dict[str, EstadoCompetencia] = Field(default_factory=dict)
    historico: list[TurnoRegistro] = Field(default_factory=list)
    item_pendente: Item | None = None
    ancoras_aplicadas: list[str] = Field(default_factory=list)
    revisao_humana: bool = False
    encerrada: bool = False
    criada_em: datetime
    atualizada_em: datetime

    # Leitura e escrita são métodos distintos de propósito. O motor de decisão só lê:
    # se ele pudesse criar entradas por acidente, `decidir_proximo_passo` deixaria de ser
    # puro e o reprocessamento (P5) passaria a depender da ordem das chamadas.

    @model_validator(mode="after")
    def _bloco_corrente_pertence_a_ordem(self) -> "AssessmentState":
        """`bloco_corrente` fora de `ordem_dos_blocos` cria um bloco fantasma.

        A sessão passaria por um bloco que não está no percurso sorteado, e o candidato
        responderia perguntas que ninguém contou. Falha explícita (P8) em vez de silêncio.
        """
        if self.ordem_dos_blocos and self.bloco_corrente not in self.ordem_dos_blocos:
            raise ValueError(
                f"bloco_corrente {self.bloco_corrente!r} não está em ordem_dos_blocos "
                f"{self.ordem_dos_blocos!r}"
            )
        return self

    def estado_do_bloco(self, bloco: str) -> EstadoBloco:
        """Leitura. Devolve um estado zerado para bloco desconhecido, sem registrá-lo."""
        return self.blocos.get(bloco) or EstadoBloco(bloco=bloco)

    def estado_da_competencia(self, competencia: str) -> EstadoCompetencia:
        """Leitura. Devolve um estado zerado para competência desconhecida, sem registrá-la."""
        return self.competencias.get(competencia) or EstadoCompetencia(competencia=competencia)

    def garantir_bloco(self, bloco: str) -> EstadoBloco:
        """Escrita. Cria e registra o estado do bloco se ainda não existir."""
        if bloco not in self.blocos:
            self.blocos[bloco] = EstadoBloco(bloco=bloco)
        return self.blocos[bloco]

    def garantir_competencia(self, competencia: str) -> EstadoCompetencia:
        """Escrita. Cria e registra o estado da competência se ainda não existir."""
        if competencia not in self.competencias:
            self.competencias[competencia] = EstadoCompetencia(competencia=competencia)
        return self.competencias[competencia]

    def blocos_pendentes(self) -> list[str]:
        """Blocos ainda não concluídos, na ordem sorteada para esta sessão."""
        return [
            bloco
            for bloco in self.ordem_dos_blocos
            if not self.blocos.get(bloco, EstadoBloco(bloco=bloco)).concluido
        ]

    def itens_ja_aplicados(self) -> set[str]:
        return {turno.item_id for turno in self.historico} | {
            item_id for estado in self.blocos.values() for item_id in estado.itens_aplicados
        }

    def houve_aquecimento(self) -> bool:
        return any(not turno.pontuou and turno.turno == 1 for turno in self.historico)
