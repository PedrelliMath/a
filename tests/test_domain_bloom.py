"""A escada de Bloom é ordenada. É a propriedade da qual todo o resto depende."""

import pytest

from app.domain.bloom import (
    BLOOM_ORDER,
    BloomLevel,
    comparar,
    descer,
    indice,
    parse,
    sao_adjacentes,
    subir,
)


class TestOrdem:
    def test_seis_niveis_na_ordem_da_taxonomia(self):
        assert [n.value for n in BLOOM_ORDER] == [
            "lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar",
        ]

    def test_indice_e_estritamente_crescente(self):
        indices = [indice(n) for n in BLOOM_ORDER]
        assert indices == sorted(indices)
        assert len(set(indices)) == len(BLOOM_ORDER)


class TestComparar:
    @pytest.mark.parametrize("esperado", BLOOM_ORDER)
    @pytest.mark.parametrize("observado", BLOOM_ORDER)
    def test_comparacao_e_monotonica(self, observado, esperado):
        """Nível mais alto nunca compara como mais baixo. Sem exceção."""
        assert comparar(observado, esperado) == (
            (indice(observado) > indice(esperado)) - (indice(observado) < indice(esperado))
        )

    def test_antissimetria(self):
        for a in BLOOM_ORDER:
            for b in BLOOM_ORDER:
                assert comparar(a, b) == -comparar(b, a)


class TestSubirDescer:
    def test_satura_no_topo(self):
        assert subir(BloomLevel.CRIAR) is BloomLevel.CRIAR

    def test_satura_no_piso(self):
        assert descer(BloomLevel.LEMBRAR) is BloomLevel.LEMBRAR

    def test_sobe_e_desce_volta_ao_mesmo_lugar(self):
        for nivel in BLOOM_ORDER[1:-1]:
            assert descer(subir(nivel)) is nivel

    def test_passos_multiplos(self):
        assert subir(BloomLevel.LEMBRAR, 3) is BloomLevel.ANALISAR
        assert subir(BloomLevel.LEMBRAR, 99) is BloomLevel.CRIAR


class TestAdjacencia:
    def test_vizinhos(self):
        assert sao_adjacentes(BloomLevel.APLICAR, BloomLevel.ANALISAR)

    def test_o_mesmo_nivel_nao_e_adjacente_a_si(self):
        assert not sao_adjacentes(BloomLevel.APLICAR, BloomLevel.APLICAR)

    def test_distantes(self):
        assert not sao_adjacentes(BloomLevel.LEMBRAR, BloomLevel.CRIAR)


class TestParse:
    def test_le_nivel_valido(self):
        assert parse("Analisar") is BloomLevel.ANALISAR

    def test_nivel_desconhecido_devolve_none(self):
        """O v1 caía em 'analisar' e fabricava medição a partir de erro de parsing."""
        assert parse("inexistente") is None

    def test_vazio_devolve_none(self):
        assert parse("") is None
