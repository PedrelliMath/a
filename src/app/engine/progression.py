"""O motor de decisão. É aqui que o código decide (P1).

`decidir_proximo_passo(estado, item, evidencia) -> Decisao` é a **fronteira estável** entre
a regra v2.0 (concordância entre observações) e a v2.1 (erro padrão abaixo de um limiar,
com modelo 1PL). A v2.1 troca só a implementação interna deste módulo; a assinatura não muda.

Nenhum agente participa desta função. Ela é determinística, não faz I/O e não conhece
`Session`, banco nem HTTP: dado o mesmo estado e a mesma evidência, devolve sempre a mesma
decisão. É isso que torna `/reprocess` possível (P5).

Implementa o fluxograma da spec §5.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.bloom import BloomLevel, comparar, descer, subir
from app.domain.evidence import Evidencia
from app.domain.items import Item
from app.domain.state import AssessmentState, MotivoConclusaoBloco
from app.engine.agreement import ha_concordancia
from app.engine.config import PARAMETROS_PADRAO, ParametrosProgressao
from app.engine.observation import (
    anti_criterio_fatal,
    conta_como_observacao,
    nivel_observado,
)


class Acao(StrEnum):
    CONTINUAR_NO_BLOCO = "continuar_no_bloco"
    TROCAR_DE_BLOCO = "trocar_de_bloco"
    ENCERRAR_SESSAO = "encerrar_sessao"


class Movimento(StrEnum):
    """Para onde vai a próxima célula, dentro do mesmo bloco."""

    SUBIR = "subir"
    MANTER = "manter"
    DESCER = "descer"


@dataclass(frozen=True)
class Decisao:
    """O que fazer a seguir. Estrutura, não texto — nada aqui é interpretado por LLM."""

    acao: Acao
    pontuou: bool
    movimento: Movimento | None = None
    bloco_alvo: str | None = None
    bloom_alvo: BloomLevel | None = None
    motivo_conclusao: MotivoConclusaoBloco | None = None
    revisao_humana: bool = False
    niveis_observados: dict[str, BloomLevel] = field(default_factory=dict)
    baixa_precisao: bool = False


def _proximo_bloco(estado: AssessmentState, bloco_atual: str) -> str | None:
    """Próximo bloco pendente na ordem sorteada para esta sessão."""
    for bloco in estado.blocos_pendentes():
        if bloco != bloco_atual:
            return bloco
    return None


def _encerrar_bloco(
    estado: AssessmentState,
    bloco: str,
    motivo: MotivoConclusaoBloco,
    pontuou: bool,
    niveis: dict[str, BloomLevel],
    revisao_humana: bool = False,
    baixa_precisao: bool = False,
) -> Decisao:
    """Bloco concluído: troca para o próximo pendente, ou encerra a sessão."""
    alvo = _proximo_bloco(estado, bloco)

    if alvo is None:
        return Decisao(
            acao=Acao.ENCERRAR_SESSAO,
            pontuou=pontuou,
            motivo_conclusao=motivo,
            revisao_humana=revisao_humana,
            niveis_observados=niveis,
            baixa_precisao=baixa_precisao,
        )

    return Decisao(
        acao=Acao.TROCAR_DE_BLOCO,
        pontuou=pontuou,
        bloco_alvo=alvo,
        bloom_alvo=estado.estado_do_bloco(alvo).bloom_corrente,
        motivo_conclusao=motivo,
        revisao_humana=revisao_humana,
        niveis_observados=niveis,
        baixa_precisao=baixa_precisao,
    )


def _movimento_de_celula(item: Item, niveis: dict[str, BloomLevel]) -> Movimento:
    """Compara o nível observado com o nível do item.

    Com várias competências no mesmo item, usa a **mediana** das comparações: uma única
    competência acima ou abaixo não move a célula sozinha. É mais estável que a média e
    não é dominada por um outlier.
    """
    if not niveis:
        return Movimento.MANTER

    comparacoes = sorted(comparar(nivel, item.bloom) for nivel in niveis.values())
    mediana = comparacoes[len(comparacoes) // 2]

    if mediana > 0:
        return Movimento.SUBIR
    if mediana < 0:
        return Movimento.DESCER
    return Movimento.MANTER


def _aplicar_movimento(bloom: BloomLevel, movimento: Movimento) -> BloomLevel:
    if movimento is Movimento.SUBIR:
        return subir(bloom)
    if movimento is Movimento.DESCER:
        return descer(bloom)
    return bloom


def decidir_proximo_passo(
    estado: AssessmentState,
    item: Item,
    evidencia: Evidencia,
    parametros: ParametrosProgressao = PARAMETROS_PADRAO,
) -> Decisao:
    """Decide o passo seguinte a partir do estado e da evidência do turno.

    Função pura: não muta `estado`. Quem aplica a decisão é `aplicar_decisao`.
    """
    bloco = item.bloco
    estado_bloco = estado.estado_do_bloco(bloco)
    niveis = nivel_observado(item, evidencia)

    # Aquecimento nunca pontua. Elimina, para todos igualmente, a penalidade da primeira
    # resposta — quando a pessoa ainda está calibrando o formato esperado (§6.1).
    if item.aquecimento:
        return Decisao(
            acao=Acao.CONTINUAR_NO_BLOCO,
            pontuou=False,
            movimento=Movimento.MANTER,
            bloco_alvo=bloco,
            bloom_alvo=estado_bloco.bloom_corrente,
        )

    # Desvio, skip ou resposta vazia: não conta como observação e não move a célula.
    if not conta_como_observacao(evidencia, parametros.confianca_baixa_nao_conta):
        return Decisao(
            acao=Acao.CONTINUAR_NO_BLOCO,
            pontuou=False,
            movimento=Movimento.MANTER,
            bloco_alvo=bloco,
            bloom_alvo=estado_bloco.bloom_corrente,
            niveis_observados=niveis,
        )

    # Anti-critério fatal encerra o bloco e chama revisão humana. O sistema não decide
    # sozinho sobre um sinal desses.
    if anti_criterio_fatal(item, evidencia) is not None:
        return _encerrar_bloco(
            estado, bloco, "anti_criterio_fatal", True, niveis, revisao_humana=True
        )

    turnos_pontuados = estado_bloco.turnos_pontuados + 1

    # Abaixo do mínimo, o bloco continua mesmo que as observações já concordem.
    if turnos_pontuados < parametros.min_turnos_bloco:
        return _continuar(estado_bloco, item, niveis)

    # Concordância por competência: o bloco fecha quando toda competência sondada
    # convergiu. Uma competência ainda ambígua segura o bloco.
    if _todas_concordam(estado, item, niveis, parametros):
        return _encerrar_bloco(estado, bloco, "evidencia_concordante", True, niveis)

    # Teto duro: encerra, mas marca que a estimativa saiu com baixa precisão.
    if turnos_pontuados >= parametros.teto_turnos_bloco:
        return _encerrar_bloco(
            estado, bloco, "teto_de_itens", True, niveis, baixa_precisao=True
        )

    return _continuar(estado_bloco, item, niveis)


def _continuar(estado_bloco, item: Item, niveis: dict[str, BloomLevel]) -> Decisao:
    movimento = _movimento_de_celula(item, niveis)
    return Decisao(
        acao=Acao.CONTINUAR_NO_BLOCO,
        pontuou=True,
        movimento=movimento,
        bloco_alvo=item.bloco,
        bloom_alvo=_aplicar_movimento(estado_bloco.bloom_corrente, movimento),
        niveis_observados=niveis,
    )


def _todas_concordam(
    estado: AssessmentState,
    item: Item,
    niveis: dict[str, BloomLevel],
    parametros: ParametrosProgressao,
) -> bool:
    """True quando toda competência sondada pelo item tem observações concordantes."""
    if not niveis:
        return False

    for competencia, nivel in niveis.items():
        historico = list(estado.estado_da_competencia(competencia).observacoes) + [nivel]
        if not ha_concordancia(historico, parametros):
            return False
    return True
