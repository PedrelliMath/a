"""A regra de parada (spec §5.1).

Em uma frase: para quando duas observações independentes caem no mesmo lugar, insiste
quando divergem. Estes testes travam exatamente isso.
"""

import pytest

from app.domain.bloom import BloomLevel
from app.domain.items import AntiCriterio
from app.engine.apply import aplicar_decisao
from app.engine.config import ParametrosProgressao
from app.engine.progression import Acao, Movimento, decidir_proximo_passo
from tests.factories import estado as novo_estado
from tests.factories import evidencia, item


def _rodar_turno(est, it, ev, parametros=None):
    kwargs = {"parametros": parametros} if parametros else {}
    decisao = decidir_proximo_passo(est, it, ev, **kwargs)
    aplicar_decisao(est, it, ev, decisao, resposta_do_candidato="resposta", **kwargs)
    return decisao


class TestAquecimento:
    def test_aquecimento_nao_pontua(self):
        """§6.1: elimina, para todos igualmente, a penalidade da primeira resposta."""
        est = novo_estado()
        d = _rodar_turno(est, item(aquecimento=True), evidencia())

        assert d.pontuou is False
        assert d.acao is Acao.CONTINUAR_NO_BLOCO
        assert est.estado_do_bloco("bloco-a").turnos_pontuados == 0

    def test_aquecimento_nao_gera_observacao(self):
        est = novo_estado()
        _rodar_turno(est, item(aquecimento=True), evidencia())
        assert est.competencias == {}


class TestDesvios:
    def test_resposta_fora_do_escopo_nao_conta(self):
        est = novo_estado()
        d = _rodar_turno(est, item(), evidencia(respondeu=False))

        assert d.pontuou is False
        assert d.movimento is Movimento.MANTER
        assert est.estado_do_bloco("bloco-a").turnos_pontuados == 0

    def test_baixa_confianca_nao_conta_como_observacao(self):
        """Contá-la faria duas leituras incertas 'concordarem' e fecharem o bloco cedo."""
        est = novo_estado()
        d = _rodar_turno(est, item(), evidencia(confianca="baixa"))
        assert d.pontuou is False

    def test_baixa_confianca_conta_se_o_parametro_permitir(self):
        est = novo_estado()
        params = ParametrosProgressao(confianca_baixa_nao_conta=False)
        d = _rodar_turno(est, item(), evidencia(confianca="baixa"), params)
        assert d.pontuou is True


class TestMinimoDeTurnos:
    def test_nunca_conclui_antes_do_minimo(self):
        """Mesmo com a primeira observação já 'boa', o bloco continua."""
        est = novo_estado()
        d = _rodar_turno(est, item(id="i1"), evidencia())

        assert d.acao is Acao.CONTINUAR_NO_BLOCO
        assert est.estado_do_bloco("bloco-a").concluido is False


class TestConcordancia:
    def test_duas_observacoes_iguais_encerram_o_bloco(self):
        est = novo_estado()
        _rodar_turno(est, item(id="i1"), evidencia())
        d = _rodar_turno(est, item(id="i2"), evidencia())

        assert d.motivo_conclusao == "evidencia_concordante"
        assert d.acao is Acao.TROCAR_DE_BLOCO
        assert d.bloco_alvo == "bloco-b"
        assert est.estado_do_bloco("bloco-a").concluido is True

    def test_observacoes_divergentes_insistem(self):
        """Uma resposta em 'aplicar' e outra acima: não se sabe onde a pessoa está."""
        est = novo_estado()
        _rodar_turno(est, item(id="i1"), evidencia(gates={"colaboracao": True}))
        d = _rodar_turno(est, item(id="i2"), evidencia(gates={"colaboracao": False}))

        assert d.acao is Acao.CONTINUAR_NO_BLOCO
        assert d.motivo_conclusao is None
        assert est.estado_do_bloco("bloco-a").concluido is False

    def test_terceira_observacao_desempata(self):
        est = novo_estado()
        _rodar_turno(est, item(id="i1"), evidencia(gates={"colaboracao": True}))
        _rodar_turno(est, item(id="i2"), evidencia(gates={"colaboracao": False}))
        d = _rodar_turno(est, item(id="i3"), evidencia(gates={"colaboracao": False}))

        assert d.motivo_conclusao == "evidencia_concordante"

    def test_uma_competencia_ambigua_segura_o_bloco(self):
        """Item que sonda duas competências: uma convergiu, a outra não."""
        est = novo_estado()
        it = item(competencias=["colaboracao", "empatia"])

        _rodar_turno(est, item(id="i1", competencias=["colaboracao", "empatia"]),
                     evidencia(gates={"colaboracao": True, "empatia": True}))
        d = _rodar_turno(est, item(id="i2", competencias=["colaboracao", "empatia"]),
                         evidencia(gates={"colaboracao": True, "empatia": False}))

        assert d.acao is Acao.CONTINUAR_NO_BLOCO
        assert it is not None


class TestTeto:
    def test_teto_encerra_e_marca_baixa_precisao(self):
        """Alternando gates, nunca há concordância: o teto tem que cortar."""
        est = novo_estado()
        params = ParametrosProgressao(min_turnos_bloco=2, teto_turnos_bloco=4)

        gates = [True, False, True, False]
        decisoes = [
            _rodar_turno(est, item(id=f"i{n}"), evidencia(gates={"colaboracao": g}), params)
            for n, g in enumerate(gates)
        ]

        assert decisoes[-1].motivo_conclusao == "teto_de_itens"
        assert decisoes[-1].baixa_precisao is True

    def test_teto_menor_que_minimo_e_rejeitado(self):
        with pytest.raises(ValueError, match="teto_turnos_bloco"):
            ParametrosProgressao(min_turnos_bloco=4, teto_turnos_bloco=2)


class TestAntiCriterioFatal:
    def test_encerra_o_bloco_e_marca_revisao_humana(self):
        est = novo_estado()
        it = item(anti_criterios=[AntiCriterio(id="a1", descricao="grave", fatal=True)])
        d = _rodar_turno(est, it, evidencia(anti_criterios=["a1"]))

        assert d.motivo_conclusao == "anti_criterio_fatal"
        assert d.revisao_humana is True
        assert est.revisao_humana is True

    def test_anti_criterio_nao_fatal_nao_encerra(self):
        est = novo_estado()
        it = item(anti_criterios=[AntiCriterio(id="a1", descricao="leve", fatal=False)])
        d = _rodar_turno(est, it, evidencia(anti_criterios=["a1"]))

        assert d.motivo_conclusao is None


class TestMovimentoDeCelula:
    def test_gate_atendido_mantem_a_celula(self):
        est = novo_estado()
        d = decidir_proximo_passo(est, item(bloom=BloomLevel.APLICAR), evidencia())
        assert d.movimento is Movimento.MANTER

    def test_gate_nao_atendido_desce(self):
        est = novo_estado()
        d = decidir_proximo_passo(
            est, item(bloom=BloomLevel.APLICAR), evidencia(gates={"colaboracao": False})
        )
        assert d.movimento is Movimento.DESCER
        assert d.bloom_alvo is BloomLevel.COMPREENDER

    def test_uma_competencia_discordante_nao_move_sozinha(self):
        """Mediana, não média: um outlier não arrasta a célula."""
        est = novo_estado()
        it = item(competencias=["a", "b", "c"])
        d = decidir_proximo_passo(
            est, it, evidencia(gates={"a": True, "b": True, "c": False})
        )
        assert d.movimento is Movimento.MANTER


class TestFimDaSessao:
    def test_ultimo_bloco_concluido_encerra_a_sessao(self):
        est = novo_estado(blocos=["bloco-a"])
        _rodar_turno(est, item(id="i1"), evidencia())
        d = _rodar_turno(est, item(id="i2"), evidencia())

        assert d.acao is Acao.ENCERRAR_SESSAO
        assert est.encerrada is True

    def test_troca_para_o_proximo_bloco_pendente(self):
        est = novo_estado(blocos=["bloco-a", "bloco-b", "bloco-c"])
        _rodar_turno(est, item(id="i1"), evidencia())
        _rodar_turno(est, item(id="i2"), evidencia())

        assert est.bloco_corrente == "bloco-b"
        assert est.encerrada is False


class TestPureza:
    def test_decidir_nao_muta_o_estado(self):
        """Decidir é puro; só `aplicar_decisao` muta. É o que torna /reprocess possível."""
        est = novo_estado()
        antes = est.model_dump_json()
        decidir_proximo_passo(est, item(), evidencia())
        assert est.model_dump_json() == antes

    def test_a_mesma_entrada_da_a_mesma_decisao(self):
        est = novo_estado()
        it, ev = item(), evidencia()
        assert decidir_proximo_passo(est, it, ev) == decidir_proximo_passo(est, it, ev)
