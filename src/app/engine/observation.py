"""Deriva o nível de Bloom observado a partir da evidência. Código puro.

O avaliador entrega evidência por critério e o gate por competência; ele **não** entrega
nível (P1). A tradução de evidência para nível acontece aqui, onde é legível, testável e
auditável — e não dentro de um prompt.

REGRA, e ela é uma suposição a validar:
    gate atendido   → a pessoa demonstrou o que o item pedia → nível observado = bloom do item
    gate não atendido → nível observado = um degrau abaixo do item

O item é calibrado num nível; atender ao seu gate é a definição operacional de operar
naquele nível. A regra é deliberadamente simples, porque uma regra que ninguém consegue
explicar a um candidato não é defensável.

Isto precisa ser conferido contra as marcações humanas da Fase 0 (spec §12.1) antes de
valer como medição. Enquanto não for, é uma hipótese explícita — não um fato.
"""

from __future__ import annotations

from app.domain.bloom import BloomLevel, descer
from app.domain.evidence import Evidencia
from app.domain.items import Item


def nivel_observado(item: Item, evidencia: Evidencia) -> dict[str, BloomLevel]:
    """Nível observado por competência individual, para um turno."""
    if not evidencia.respondeu_a_pergunta:
        return {}

    observados: dict[str, BloomLevel] = {}
    for competencia in item.competencias:
        atendeu = evidencia.gate_por_competencia.get(competencia, False)
        observados[competencia] = item.bloom if atendeu else descer(item.bloom)
    return observados


def conta_como_observacao(
    evidencia: Evidencia,
    confianca_baixa_nao_conta: bool,
) -> bool:
    """Se esta evidência entra na contagem de concordância.

    Evidência de baixa confiança não conta: contá-la faria duas leituras incertas
    "concordarem" e encerrarem o bloco cedo, que é exatamente o erro que a regra existe
    para evitar.
    """
    if not evidencia.respondeu_a_pergunta:
        return False
    if confianca_baixa_nao_conta and evidencia.confianca == "baixa":
        return False
    return True


def anti_criterio_fatal(item: Item, evidencia: Evidencia) -> str | None:
    """Devolve o id do anti-critério fatal detectado, se houver.

    Anti-critério fatal encerra o bloco e marca a sessão para revisão humana. O sistema
    não decide sozinho sobre um sinal desses.
    """
    for detectado in evidencia.anti_criterios:
        anti = item.anti_criterio(detectado.anti_criterio_id)
        if anti is not None and anti.fatal:
            return anti.id
    return None
