"""O estado é a única fonte de verdade (P3) e o insumo do reprocessamento (P5)."""

from app.domain.bloom import BloomLevel
from app.domain.state import AssessmentState
from app.engine.apply import aplicar_decisao
from app.engine.progression import decidir_proximo_passo
from tests.factories import estado as novo_estado
from tests.factories import evidencia, item


def _turno(est, it, ev):
    aplicar_decisao(est, it, ev, decidir_proximo_passo(est, it, ev), resposta_do_candidato="r")


class TestHistorico:
    def test_todo_turno_vira_registro_de_auditoria(self):
        est = novo_estado()
        _turno(est, item(id="i1"), evidencia())

        registro = est.historico[0]
        assert registro.turno == 1
        assert registro.item_id == "i1"
        assert registro.enunciado_apresentado == "Enunciado fixo de i1."
        assert registro.resposta_do_candidato == "r"
        assert registro.nivel_observado == {"colaboracao": BloomLevel.APLICAR}

    def test_o_desvio_tambem_e_registrado(self):
        """Não pontua, mas fica no log: o que aconteceu na sessão precisa ser reconstituível."""
        est = novo_estado()
        _turno(est, item(id="i1"), evidencia(respondeu=False))

        assert len(est.historico) == 1
        assert est.historico[0].pontuou is False


class TestCompetencias:
    def test_nivel_por_competencia_e_acumulado(self):
        """É o dado que o v1 produzia e descartava."""
        est = novo_estado()
        _turno(est, item(id="i1", competencias=["colaboracao", "empatia"]),
               evidencia(gates={"colaboracao": True, "empatia": False}))

        assert est.competencias["colaboracao"].observacoes == [BloomLevel.APLICAR]
        assert est.competencias["empatia"].observacoes == [BloomLevel.COMPREENDER]

    def test_concordancia_e_marcada(self):
        est = novo_estado()
        _turno(est, item(id="i1"), evidencia())
        assert est.competencias["colaboracao"].concordante is False

        _turno(est, item(id="i2"), evidencia())
        assert est.competencias["colaboracao"].concordante is True
        assert est.competencias["colaboracao"].nivel_estimado is BloomLevel.APLICAR

    def test_sem_concordancia_o_nivel_sai_incerto(self):
        est = novo_estado()
        _turno(est, item(id="i1"), evidencia(gates={"colaboracao": True}))
        _turno(est, item(id="i2"), evidencia(gates={"colaboracao": False}))

        competencia = est.competencias["colaboracao"]
        assert competencia.concordante is False
        assert competencia.nivel_estimado is BloomLevel.COMPREENDER


class TestSerializacao:
    def test_o_estado_sobrevive_a_uma_volta_por_json(self):
        """É serializado inteiro em JSONB e é a única coisa necessária para retomar."""
        est = novo_estado()
        _turno(est, item(id="i1"), evidencia())

        recuperado = AssessmentState.model_validate_json(est.model_dump_json())

        assert recuperado.historico[0].item_id == "i1"
        assert recuperado.competencias["colaboracao"].observacoes == [BloomLevel.APLICAR]
        assert recuperado.ordem_dos_blocos == est.ordem_dos_blocos


class TestReprocessamento:
    def test_replicar_os_turnos_reproduz_o_estado(self):
        """P5: dado o histórico, o resultado é recomputável sem chamar LLM."""
        original = novo_estado(blocos=["bloco-a", "bloco-b"])
        turnos = [
            (item(id="i1"), evidencia(gates={"colaboracao": True})),
            (item(id="i2"), evidencia(gates={"colaboracao": False})),
            (item(id="i3"), evidencia(gates={"colaboracao": False})),
        ]
        for it, ev in turnos:
            _turno(original, it, ev)

        replica = novo_estado(blocos=["bloco-a", "bloco-b"])
        for it, ev in turnos:
            _turno(replica, it, ev)

        assert replica.competencias["colaboracao"].observacoes == (
            original.competencias["colaboracao"].observacoes
        )
        assert replica.bloco_corrente == original.bloco_corrente
        assert replica.blocos["bloco-a"].motivo_conclusao == (
            original.blocos["bloco-a"].motivo_conclusao
        )
