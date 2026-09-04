"""A regra de concordância — o coração da regra de parada v2.0 (spec §5.1).

Em uma frase: **para quando duas observações independentes caem no mesmo lugar, insiste
quando divergem.** Uma resposta em "aplicar" e outra em "criar" significa que você não sabe
onde a pessoa está, então faz a terceira, que desempata.

A intenção que o time descreveu — "encontrar boa evidência de que o candidato sabe algo e
passar adiante" — não é subjetiva, estava indefinida. Isto é a definição operacional dela,
e não precisa de item calibrado para funcionar.
"""

from __future__ import annotations

from app.domain.bloom import BloomLevel, indice, sao_adjacentes
from app.engine.config import PARAMETROS_PADRAO, ParametrosProgressao


def concordam(
    a: BloomLevel,
    b: BloomLevel,
    parametros: ParametrosProgressao = PARAMETROS_PADRAO,
) -> bool:
    """Duas observações concordam se caem no mesmo nível — ou vizinhas, se tolerado."""
    if a == b:
        return True
    return parametros.tolera_adjacente and sao_adjacentes(a, b)


def ha_concordancia(
    observacoes: list[BloomLevel],
    parametros: ParametrosProgressao = PARAMETROS_PADRAO,
) -> bool:
    """True quando as N últimas observações concordam entre si.

    Com menos de N observações não há como concordar: devolve False, e o bloco continua.
    """
    n = parametros.concordancia_exige_n
    if len(observacoes) < n:
        return False

    ultimas = observacoes[-n:]
    referencia = ultimas[0]
    return all(concordam(referencia, outra, parametros) for outra in ultimas[1:])


def nivel_concordante(
    observacoes: list[BloomLevel],
    parametros: ParametrosProgressao = PARAMETROS_PADRAO,
) -> BloomLevel | None:
    """O nível em que as observações convergiram, ou None se ainda divergem.

    Com `tolera_adjacente` ligado, duas observações vizinhas convergem para a **mais baixa**.
    É uma escolha conservadora e deliberada: o nível afirmado é o que a evidência sustenta
    sem ambiguidade. Registrar essa preferência aqui, e não no prompt, é o que a torna
    auditável.
    """
    if not ha_concordancia(observacoes, parametros):
        return None

    ultimas = observacoes[-parametros.concordancia_exige_n :]
    return min(ultimas, key=indice)
