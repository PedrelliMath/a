"""Aplica uma `Decisao` ao estado. Separado de `decidir_proximo_passo` de propósito.

Decidir é uma função pura; aplicar é a única coisa que muta o estado. Manter os dois
separados é o que permite reprocessar uma sessão inteira a partir de `turns`, replicando
as decisões sem chamar LLM (P5), e testar a decisão sem montar estado mutável.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.bloom import BloomLevel
from app.domain.evidence import Evidencia
from app.domain.items import Item
from app.domain.state import AssessmentState, TurnoRegistro
from app.engine.agreement import nivel_concordante
from app.engine.config import PARAMETROS_PADRAO, ParametrosProgressao
from app.engine.progression import Acao, Decisao


def aplicar_decisao(
    estado: AssessmentState,
    item: Item,
    evidencia: Evidencia,
    decisao: Decisao,
    resposta_do_candidato: str,
    mensagem_do_supervisor: str = "",
    momento: datetime | None = None,
    parametros: ParametrosProgressao = PARAMETROS_PADRAO,
) -> AssessmentState:
    """Registra o turno e move o estado. Muta e devolve `estado`."""
    agora = momento or datetime.now(timezone.utc)
    estado_bloco = estado.garantir_bloco(item.bloco)

    estado.historico.append(
        TurnoRegistro(
            turno=len(estado.historico) + 1,
            item_id=item.id,
            item_versao=item.versao,
            bloco=item.bloco,
            bloom=item.bloom,
            enunciado_apresentado=item.enunciado,
            mensagem_do_supervisor=mensagem_do_supervisor,
            resposta_do_candidato=resposta_do_candidato,
            evidencia=evidencia,
            nivel_observado=decisao.niveis_observados,
            pontuou=decisao.pontuou,
            timestamp=agora,
        )
    )

    if item.id not in estado_bloco.itens_aplicados:
        estado_bloco.itens_aplicados.append(item.id)
    if item.ancora and item.id not in estado.ancoras_aplicadas:
        estado.ancoras_aplicadas.append(item.id)

    if decisao.pontuou:
        estado_bloco.turnos_pontuados += 1
        _registrar_observacoes(estado, decisao.niveis_observados, parametros)

    if decisao.revisao_humana:
        estado.revisao_humana = True

    if decisao.acao is Acao.CONTINUAR_NO_BLOCO:
        if decisao.bloom_alvo is not None:
            estado_bloco.bloom_corrente = decisao.bloom_alvo
    else:
        estado_bloco.concluido = True
        estado_bloco.motivo_conclusao = decisao.motivo_conclusao

        if decisao.acao is Acao.TROCAR_DE_BLOCO and decisao.bloco_alvo is not None:
            estado.bloco_corrente = decisao.bloco_alvo
            if decisao.bloom_alvo is not None:
                estado.garantir_bloco(decisao.bloco_alvo).bloom_corrente = decisao.bloom_alvo
        elif decisao.acao is Acao.ENCERRAR_SESSAO:
            estado.encerrada = True

    estado.item_pendente = None
    estado.atualizada_em = agora
    return estado


def _registrar_observacoes(
    estado: AssessmentState,
    niveis: dict[str, BloomLevel],
    parametros: ParametrosProgressao,
) -> None:
    for competencia, nivel in niveis.items():
        estado_competencia = estado.garantir_competencia(competencia)
        estado_competencia.observacoes.append(nivel)

        convergiu = nivel_concordante(estado_competencia.observacoes, parametros)
        estado_competencia.concordante = convergiu is not None
        # Sem concordância, o nível estimado é a última observação: é o melhor palpite
        # disponível, e `concordante=False` diz ao relatório que ele é incerto.
        estado_competencia.nivel_estimado = convergiu or nivel
