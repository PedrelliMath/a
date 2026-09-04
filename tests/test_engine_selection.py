"""Seleção de item: mesmo estímulo na mesma posição (P6), e falha alta em célula vazia."""

import pytest

from app.domain.bloom import BloomLevel
from app.domain.items import ItemFormat
from app.engine.selection import CelulaVaziaError, selecionar_item
from tests.factories import estado as novo_estado
from tests.factories import evidencia, item
from app.engine.apply import aplicar_decisao
from app.engine.progression import decidir_proximo_passo


def _banco():
    return [
        item(id="a-aplicar-1", bloom=BloomLevel.APLICAR, formato=ItemFormat.CENARIO),
        item(id="a-aplicar-2", bloom=BloomLevel.APLICAR, formato=ItemFormat.CRITICA),
        item(id="a-aplicar-3", bloom=BloomLevel.APLICAR, formato=ItemFormat.TRADEOFF),
        item(id="a-analisar-1", bloom=BloomLevel.ANALISAR, formato=ItemFormat.CENARIO),
    ]


class TestDeterminismo:
    def test_dois_candidatos_na_mesma_celula_recebem_o_mesmo_item(self):
        """P6. Não há correção estatística que equipare estímulos que nunca foram iguais."""
        escolhido = {
            selecionar_item(_banco(), novo_estado(), "bloco-a", BloomLevel.APLICAR).id
            for _ in range(50)
        }
        assert len(escolhido) == 1

    def test_o_enunciado_e_fixo(self):
        it = selecionar_item(_banco(), novo_estado(), "bloco-a", BloomLevel.APLICAR)
        assert it.enunciado == f"Enunciado fixo de {it.id}."


class TestNaoRepeticao:
    def test_nao_repete_item_ja_aplicado(self):
        est = novo_estado()
        banco = _banco()

        primeiro = selecionar_item(banco, est, "bloco-a", BloomLevel.APLICAR)
        ev = evidencia()
        aplicar_decisao(
            est, primeiro, ev, decidir_proximo_passo(est, primeiro, ev),
            resposta_do_candidato="r",
        )

        segundo = selecionar_item(banco, est, "bloco-a", BloomLevel.APLICAR)
        assert segundo.id != primeiro.id

    def test_prefere_formato_diferente_do_ultimo(self):
        """Três DIRETA seguidos viram formulário."""
        est = novo_estado()
        banco = _banco()

        primeiro = selecionar_item(banco, est, "bloco-a", BloomLevel.APLICAR)
        ev = evidencia()
        aplicar_decisao(
            est, primeiro, ev, decidir_proximo_passo(est, primeiro, ev),
            resposta_do_candidato="r",
        )

        segundo = selecionar_item(banco, est, "bloco-a", BloomLevel.APLICAR)
        assert segundo.formato is not primeiro.formato


class TestCelulaVazia:
    def test_celula_inexistente_falha_alto(self):
        """§16: célula sem item é erro de configuração, não condição de runtime.

        Nada de fallback gerando pergunta — improvisar estímulo contamina a medição.
        """
        with pytest.raises(CelulaVaziaError) as exc:
            selecionar_item(_banco(), novo_estado(), "bloco-a", BloomLevel.CRIAR)

        assert "erro de configuração" in str(exc.value)

    def test_celula_esgotada_falha_alto(self):
        est = novo_estado()
        banco = [item(id="unico", bloom=BloomLevel.APLICAR)]
        ev = evidencia()
        aplicar_decisao(
            est, banco[0], ev, decidir_proximo_passo(est, banco[0], ev),
            resposta_do_candidato="r",
        )

        with pytest.raises(CelulaVaziaError):
            selecionar_item(banco, est, "bloco-a", BloomLevel.APLICAR)
