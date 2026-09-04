"""Fábricas para montar estado e itens nos testes, sem repetir boilerplate."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.bloom import BloomLevel
from app.domain.evidence import Evidencia
from app.domain.items import AntiCriterio, Criterio, Item, ItemFormat
from app.domain.state import AssessmentState


def item(
    id: str = "item-1",
    bloco: str = "bloco-a",
    competencias: list[str] | None = None,
    bloom: BloomLevel = BloomLevel.APLICAR,
    formato: ItemFormat = ItemFormat.CENARIO,
    aquecimento: bool = False,
    ancora: bool = False,
    anti_criterios: list[AntiCriterio] | None = None,
) -> Item:
    comps = competencias if competencias is not None else ["colaboracao"]
    return Item(
        id=id,
        bloco=bloco,
        competencias=comps,
        bloom=bloom,
        formato=formato,
        enunciado=f"Enunciado fixo de {id}.",
        intencao="Demonstrar a operação cognitiva do nível.",
        criterios=[
            Criterio(
                id=f"{id}-c1",
                competencia=comps[0],
                descricao="Critério de teste",
                evidencia_gate="cita uma situação real com resultado observável",
            )
        ],
        anti_criterios=anti_criterios or [],
        aquecimento=aquecimento,
        ancora=ancora,
    )


def evidencia(
    respondeu: bool = True,
    gates: dict[str, bool] | None = None,
    confianca: str = "alta",
    anti_criterios: list[str] | None = None,
) -> Evidencia:
    from app.domain.evidence import AntiCriterioDetectado

    return Evidencia(
        respondeu_a_pergunta=respondeu,
        motivo_nao_resposta=None if respondeu else "fora_do_escopo",
        gate_por_competencia=gates if gates is not None else {"colaboracao": True},
        confianca=confianca,
        anti_criterios=[
            AntiCriterioDetectado(anti_criterio_id=a, trecho_citado="trecho")
            for a in (anti_criterios or [])
        ],
    )


def estado(
    blocos: list[str] | None = None,
    bloco_corrente: str | None = None,
) -> AssessmentState:
    ordem = blocos if blocos is not None else ["bloco-a", "bloco-b"]
    bloco_corrente = bloco_corrente or ordem[0]
    agora = datetime.now(timezone.utc)
    return AssessmentState(
        sessao_id=uuid4(),
        skill_id=uuid4(),
        candidato_id="candidato-1",
        ordem_dos_blocos=ordem,
        bloco_corrente=bloco_corrente,
        criada_em=agora,
        atualizada_em=agora,
    )
