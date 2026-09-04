"""Parâmetros da regra de parada (spec §5.1).

Todos vêm de config, nenhum hardcoded no meio da lógica. `TOLERA_ADJACENTE` em especial
merece um A/B contra os dados anotados: com 6 níveis, exigir concordância exata pode ser
exigente demais e estourar o teto com frequência.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParametrosProgressao(BaseModel):
    min_turnos_bloco: int = Field(default=2, ge=1, description="nunca conclui antes disso")
    teto_turnos_bloco: int = Field(default=4, ge=1, description="teto duro")
    concordancia_exige_n: int = Field(
        default=2, ge=2, description="observações consecutivas iguais"
    )
    confianca_baixa_nao_conta: bool = Field(
        default=True, description="evidência de baixa confiança não conta como observação"
    )
    tolera_adjacente: bool = Field(
        default=False, description="se True, níveis vizinhos contam como concordantes"
    )

    def model_post_init(self, _context: object) -> None:
        if self.teto_turnos_bloco < self.min_turnos_bloco:
            raise ValueError(
                f"teto_turnos_bloco ({self.teto_turnos_bloco}) não pode ser menor que "
                f"min_turnos_bloco ({self.min_turnos_bloco})"
            )


PARAMETROS_PADRAO = ParametrosProgressao()
