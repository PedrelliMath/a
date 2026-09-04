"""Seleção do próximo item. Código puro sobre o banco carregado.

Regras, em ordem:
1. Nunca repetir item já aplicado na sessão.
2. Preferir formato diferente do último item do bloco — três `DIRETA` seguidos viram
   formulário, que é a causa apontada do efeito relatado no v1.
3. Célula vazia é **erro de configuração** e falha alto (spec §16). Não existe fallback
   gerando pergunta em runtime.
"""

from __future__ import annotations

from app.domain.bloom import BloomLevel
from app.domain.items import Item, ItemFormat
from app.domain.state import AssessmentState


class CelulaVaziaError(RuntimeError):
    """Não há item disponível para a célula pedida.

    Falha explícita (P8): melhor interromper a sessão do que improvisar um estímulo e
    contaminar a medição de uma pessoa real.
    """

    def __init__(self, bloco: str, bloom: BloomLevel, restantes: int):
        self.bloco = bloco
        self.bloom = bloom
        super().__init__(
            f"Célula sem item disponível: bloco={bloco!r} bloom={bloom.value!r}. "
            f"{restantes} item(ns) existem na célula, todos já aplicados nesta sessão. "
            f"Isto é erro de configuração do banco, não condição de runtime."
        )


def itens_da_celula(banco: list[Item], bloco: str, bloom: BloomLevel) -> list[Item]:
    return [item for item in banco if item.bloco == bloco and item.bloom is bloom]


def selecionar_item(
    banco: list[Item],
    estado: AssessmentState,
    bloco: str,
    bloom: BloomLevel,
) -> Item:
    """Escolhe o próximo item da célula. Determinístico: ordena por id para desempatar.

    Determinismo aqui não é detalhe — é o que garante que dois candidatos na mesma posição
    recebem o mesmo estímulo (P6) e que a sessão é reproduzível.
    """
    da_celula = itens_da_celula(banco, bloco, bloom)
    if not da_celula:
        raise CelulaVaziaError(bloco, bloom, 0)

    aplicados = estado.itens_ja_aplicados()
    disponiveis = [item for item in da_celula if item.id not in aplicados]
    if not disponiveis:
        raise CelulaVaziaError(bloco, bloom, len(da_celula))

    ultimo_formato = _ultimo_formato_do_bloco(banco, estado, bloco)
    if ultimo_formato is not None:
        variados = [item for item in disponiveis if item.formato is not ultimo_formato]
        if variados:
            disponiveis = variados

    return sorted(disponiveis, key=lambda item: item.id)[0]


def _ultimo_formato_do_bloco(
    banco: list[Item], estado: AssessmentState, bloco: str
) -> ItemFormat | None:
    """Formato do último item aplicado neste bloco, lido do histórico.

    O histórico guarda `item_id`, não o formato; a resolução é feita contra o banco para
    não duplicar em `TurnoRegistro` um dado que já pertence ao item.
    """
    por_id = {item.id: item for item in banco}
    for turno in reversed(estado.historico):
        if turno.bloco != bloco:
            continue
        item = por_id.get(turno.item_id)
        if item is not None:
            return item.formato
    return None
