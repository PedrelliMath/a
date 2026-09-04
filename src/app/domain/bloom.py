"""Taxonomia de Bloom: a escala em que tudo neste sistema é medido.

A ordem importa e é a única fonte de verdade sobre ela. Nenhum outro módulo redefine
a lista de níveis — no v1 ela aparecia duplicada em quatro lugares.
"""

from __future__ import annotations

from enum import StrEnum


class BloomLevel(StrEnum):
    LEMBRAR = "lembrar"
    COMPREENDER = "compreender"
    APLICAR = "aplicar"
    ANALISAR = "analisar"
    AVALIAR = "avaliar"
    CRIAR = "criar"


BLOOM_ORDER: list[BloomLevel] = [
    BloomLevel.LEMBRAR,
    BloomLevel.COMPREENDER,
    BloomLevel.APLICAR,
    BloomLevel.ANALISAR,
    BloomLevel.AVALIAR,
    BloomLevel.CRIAR,
]


def indice(nivel: BloomLevel) -> int:
    """Posição do nível na escada. É o que torna a comparação ordenável."""
    return BLOOM_ORDER.index(nivel)


def comparar(observado: BloomLevel, esperado: BloomLevel) -> int:
    """-1 se o observado está abaixo do esperado, 0 se igual, 1 se acima."""
    delta = indice(observado) - indice(esperado)
    return (delta > 0) - (delta < 0)


def sao_adjacentes(a: BloomLevel, b: BloomLevel) -> bool:
    """Níveis vizinhos na escada. Usado quando `TOLERA_ADJACENTE` está ligado."""
    return abs(indice(a) - indice(b)) == 1


def subir(nivel: BloomLevel, passos: int = 1) -> BloomLevel:
    """Sobe na escada, saturando no topo. Nunca estoura."""
    return BLOOM_ORDER[min(indice(nivel) + passos, len(BLOOM_ORDER) - 1)]


def descer(nivel: BloomLevel, passos: int = 1) -> BloomLevel:
    """Desce na escada, saturando no piso. Nunca estoura."""
    return BLOOM_ORDER[max(indice(nivel) - passos, 0)]


def parse(valor: str) -> BloomLevel | None:
    """Lê um nível a partir de texto livre. Devolve None em vez de adivinhar.

    O v1 caía em "analisar" quando não reconhecia o nível, o que fabricava uma medição
    a partir de um erro de parsing. Aqui a ausência é explícita e quem chama decide (P8).
    """
    if not valor:
        return None
    candidato = valor.strip().lower()
    for nivel in BLOOM_ORDER:
        if nivel.value == candidato:
            return nivel
    return None
