"""Item bank: o instrumento de medição.

Conteúdo curado offline, versionado. **Nunca gerado em runtime** (spec §16): célula sem
item é erro de configuração e deve falhar alto, não virar uma pergunta improvisada.

`Criterio` e `AntiCriterio` são a rubrica. Eles chegam ao avaliador e a mais ninguém —
o princípio P4 proíbe que o instrumento de medição chegue parafraseado ao candidato.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.bloom import BloomLevel


class ItemFormat(StrEnum):
    CENARIO = "cenario"      # situação concreta, pede decisão
    CRITICA = "critica"      # solução ruim apresentada, pede análise
    TRADEOFF = "tradeoff"    # duas opções, pede condição de escolha
    EXTENSAO = "extensao"    # aprofunda a resposta anterior
    DIRETA = "direta"        # pergunta conceitual direta


class Criterio(BaseModel):
    """Da rubrica. NUNCA sai do avaliador."""

    id: str
    competencia: str = Field(description="competência individual, não o pacote de navegação")
    descricao: str
    evidencia_gate: str = Field(
        description="O que precisa aparecer na resposta para o critério ser atendido"
    )
    peso: float = 1.0


class AntiCriterio(BaseModel):
    """Sinal cuja presença desqualifica, independentemente do resto da resposta."""

    id: str
    descricao: str
    fatal: bool = False


class Item(BaseModel):
    """Uma pergunta fixa, versionada, com critérios anexados.

    `enunciado` é texto fixo: dois candidatos na mesma célula recebem exatamente o mesmo
    estímulo (P6). Não existe correção estatística que equipare estímulos que nunca foram
    iguais, e é por isso que o gerador de perguntas em runtime foi removido.
    """

    id: str
    bloco: str = Field(description="pacote de navegação — a macrocompetência atual")
    competencias: list[str] = Field(description="competências individuais que este item sonda")
    bloom: BloomLevel
    dificuldade: float | None = Field(
        default=None, description="logit; None até o item ser calibrado (Fase 7)"
    )
    formato: ItemFormat
    enunciado: str = Field(description="Texto fixo apresentado. Mesmo para todos os candidatos.")
    intencao: str = Field(description="O que o item quer que a pessoa demonstre. Vai ao supervisor.")
    criterios: list[Criterio] = Field(default_factory=list)
    anti_criterios: list[AntiCriterio] = Field(default_factory=list)
    ancora: bool = Field(default=False, description="se True, todo candidato vê este item")
    aquecimento: bool = Field(default=False, description="se True, não pontua")
    versao: int = 1

    @property
    def celula(self) -> tuple[str, BloomLevel]:
        """Bloco × nível de Bloom. A unidade de cobertura do banco."""
        return (self.bloco, self.bloom)

    def anti_criterio(self, anti_criterio_id: str) -> AntiCriterio | None:
        for anti in self.anti_criterios:
            if anti.id == anti_criterio_id:
                return anti
        return None
