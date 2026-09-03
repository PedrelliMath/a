"""Testes das funções puras de progressão de Bloom.

São as funções onde o código decide (P1). Nenhuma delas chama LLM, então todas
devem ser verificáveis sem rede e sem banco.
"""

import pytest

from app.ai.agents.services.agent_orquestrator import (
    get_proficiency_level,
    ordenar_blocos,
)
from app.ai.agents.skill_evaluator import (
    compare_bloom_levels,
    normalize_skill_name,
    parse_skill_group,
)

BLOOM = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]


class TestGetProficiencyLevel:
    def test_sobe_um_nivel(self):
        assert get_proficiency_level("aplicar", 1) == "analisar"

    def test_desce_um_nivel(self):
        assert get_proficiency_level("aplicar", -1) == "compreender"

    def test_mantem(self):
        assert get_proficiency_level("aplicar", 0) == "aplicar"

    def test_nao_passa_do_teto(self):
        assert get_proficiency_level("criar", 1) == "criar"

    def test_nao_passa_do_piso(self):
        assert get_proficiency_level("lembrar", -1) == "lembrar"

    def test_nivel_desconhecido_cai_no_default(self):
        assert get_proficiency_level("inexistente", 1) == "analisar"

    def test_case_insensitive(self):
        assert get_proficiency_level("ANALISAR", 1) == "avaliar"


class TestCompareBloomLevels:
    def test_igual(self):
        assert compare_bloom_levels("analisar", "analisar") == 0

    def test_abaixo(self):
        assert compare_bloom_levels("analisar", "aplicar") == -1

    def test_acima(self):
        assert compare_bloom_levels("analisar", "criar") == 1

    def test_achieved_vazio_nao_move(self):
        assert compare_bloom_levels("analisar", "") == 0

    def test_expected_invalido_nao_move(self):
        assert compare_bloom_levels("inexistente", "criar") == 0

    def test_multiplos_niveis_usa_o_mais_proximo(self):
        # "avaliar/criar" com esperado "avaliar": o mais próximo é o próprio "avaliar"
        assert compare_bloom_levels("avaliar", "avaliar/criar") == 0

    def test_a_escada_e_ordenada(self):
        """A relação precisa ser monotônica: nível mais alto nunca compara como mais baixo."""
        for i, esperado in enumerate(BLOOM):
            for j, obtido in enumerate(BLOOM):
                resultado = compare_bloom_levels(esperado, obtido)
                assert resultado == (j > i) - (j < i), f"{esperado} vs {obtido}"


class TestParseSkillGroup:
    def test_desmembra_o_bloco_em_competencias(self):
        assert parse_skill_group("Colaboração, Empatia") == ["colaboracao", "empatia"]

    def test_remove_acento_e_normaliza(self):
        assert normalize_skill_name("Dados e Inteligência Artificial") == (
            "dados_e_inteligencia_artificial"
        )

    def test_bloco_de_uma_competencia_so(self):
        assert parse_skill_group("Autoconhecimento") == ["autoconhecimento"]


class TestOrdenarBlocos:
    """C7 (spec §15): o primeiro bloco não pode ser sempre o mesmo."""

    BLOCOS = ["Autoconhecimento", "Colaboração", "Negócio", "Dados"]

    def test_determinismo(self):
        """Mesma sessão, mesma ordem. É o que torna o reprocessamento possível (P5)."""
        a = ordenar_blocos(self.BLOCOS, "9c1f2c4e-0000-0000-0000-000000000001")
        b = ordenar_blocos(self.BLOCOS, "9c1f2c4e-0000-0000-0000-000000000001")
        assert a == b

    def test_preserva_o_conjunto(self):
        ordenados = ordenar_blocos(self.BLOCOS, "qualquer-id")
        assert sorted(ordenados) == sorted(self.BLOCOS)

    def test_nao_e_sempre_o_mesmo_primeiro_bloco(self):
        """O ponto do C7: distribuir a penalidade da primeira resposta entre os blocos."""
        primeiros = {
            ordenar_blocos(self.BLOCOS, f"sessao-{i}")[0] for i in range(200)
        }
        assert len(primeiros) > 1, "a ordem não está variando entre sessões"

    def test_lista_vazia(self):
        assert ordenar_blocos([], "id") == []

    def test_bloco_unico(self):
        assert ordenar_blocos(["Único"], "id") == ["Único"]


@pytest.mark.parametrize("nivel", BLOOM)
def test_todo_nivel_de_bloom_e_reconhecido(nivel):
    assert get_proficiency_level(nivel, 0) == nivel
