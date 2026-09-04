"""Aceite da Fase 1 (spec §14): respondente sintético não produz loop nem encerramento prematuro.

Uma regra de parada pode falhar de dois jeitos opostos, e os dois são graves: nunca parar
(a pessoa responde para sempre) ou parar cedo demais (o resultado sai sem evidência).
Estes testes fecham as duas portas com respondentes de comportamentos diferentes.
"""

import random

import pytest

from app.engine.apply import aplicar_decisao
from app.engine.config import ParametrosProgressao
from app.engine.progression import decidir_proximo_passo
from tests.factories import estado as novo_estado
from tests.factories import evidencia, item

TETO_DE_SEGURANCA = 60
BLOCOS = ["b1", "b2", "b3"]


def simular(responde, sementes: int = 100, parametros=None):
    """Roda sessões completas e devolve (loops, prematuros, turnos_por_sessao)."""
    params = parametros or ParametrosProgressao()
    loops = prematuros = 0
    turnos_por_sessao = []

    for semente in range(sementes):
        rng = random.Random(semente)
        est = novo_estado(blocos=list(BLOCOS))
        turnos = 0

        while not est.encerrada and turnos < TETO_DE_SEGURANCA:
            turnos += 1
            it = item(id=f"i{turnos}", bloco=est.bloco_corrente)
            ev = evidencia(gates={"colaboracao": responde(rng, turnos)})
            decisao = decidir_proximo_passo(est, it, ev, params)
            aplicar_decisao(est, it, ev, decisao, resposta_do_candidato="r", parametros=params)

        if not est.encerrada:
            loops += 1
        if sum(1 for t in est.historico if t.pontuou) < params.min_turnos_bloco:
            prematuros += 1
        turnos_por_sessao.append(turnos)

    return loops, prematuros, turnos_por_sessao


PERFIS = {
    "sempre_atende": lambda rng, turno: True,
    "nunca_atende": lambda rng, turno: False,
    "aleatorio": lambda rng, turno: rng.random() < 0.5,
    "alternado": lambda rng, turno: turno % 2 == 0,
    "raro": lambda rng, turno: rng.random() < 0.1,
}


@pytest.mark.parametrize("nome", list(PERFIS))
def test_nenhum_perfil_produz_loop(nome):
    loops, _, _ = simular(PERFIS[nome])
    assert loops == 0, f"perfil {nome!r} não encerrou em {TETO_DE_SEGURANCA} turnos"


@pytest.mark.parametrize("nome", list(PERFIS))
def test_nenhum_perfil_encerra_prematuramente(nome):
    _, prematuros, _ = simular(PERFIS[nome])
    assert prematuros == 0, f"perfil {nome!r} encerrou antes do mínimo de turnos"


def test_o_teto_limita_a_sessao():
    """O pior caso é o respondente alternado: nunca concorda, então bate o teto sempre."""
    params = ParametrosProgressao(min_turnos_bloco=2, teto_turnos_bloco=4)
    _, _, turnos = simular(PERFIS["alternado"], parametros=params)

    maximo_teorico = len(BLOCOS) * params.teto_turnos_bloco
    assert max(turnos) <= maximo_teorico


def test_quem_concorda_sempre_faz_a_sessao_mais_curta():
    """Boa evidência logo encerra o bloco: é a intenção que o time descreveu."""
    params = ParametrosProgressao(min_turnos_bloco=2, teto_turnos_bloco=4)
    _, _, concordante = simular(PERFIS["sempre_atende"], parametros=params)
    _, _, divergente = simular(PERFIS["alternado"], parametros=params)

    assert max(concordante) < max(divergente)
    assert max(concordante) == len(BLOCOS) * params.min_turnos_bloco


def test_todos_os_blocos_sao_percorridos():
    est = novo_estado(blocos=list(BLOCOS))
    turnos = 0
    while not est.encerrada and turnos < TETO_DE_SEGURANCA:
        turnos += 1
        it = item(id=f"i{turnos}", bloco=est.bloco_corrente)
        ev = evidencia()
        decisao = decidir_proximo_passo(est, it, ev)
        aplicar_decisao(est, it, ev, decisao, resposta_do_candidato="r")

    assert all(est.blocos[bloco].concluido for bloco in BLOCOS)
