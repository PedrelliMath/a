#!/usr/bin/env python3
"""Mede a correlação entre o nível de Bloom atribuído e o tamanho da resposta.

Spec §6.3 e C3. É o primeiro script a existir porque roda com os dados que já temos e
responde a pergunta mais séria sobre o avaliador atual: ele está lendo complexidade
cognitiva, ou está lendo sofisticação verbal?

Modelos de linguagem confundem as duas coisas. Se o nível atribuído sobe com o número de
tokens da resposta, o sistema penaliza quem escreve direto, quem tem menos escolaridade
formal e registros regionais distantes do padrão culto — variância irrelevante ao construto,
num sistema que decide sobre pessoas.

Critério (spec §6.3): correlação acima de 0.4 é alerta vermelho.

Uso:
    python scripts/check_verbosity_bias.py
    python scripts/check_verbosity_bias.py --dir artifacts/observability --limiar 0.4
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

BLOOM_ORDER = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]

LIMIAR_PADRAO = 0.4
MINIMO_DE_PARES = 20


def contar_tokens(texto: str) -> int:
    """Proxy simples de extensão. Não precisa ser o tokenizer do modelo: o que importa
    é a ordem de grandeza, e qualquer medida monotônica de tamanho serve."""
    return len(re.findall(r"\w+", texto or ""))


def extrair_nivel(avaliacao: str) -> int | None:
    """Lê `obtido=<nivel>` do campo `avaliacao_valuator` e devolve o índice na escala."""
    match = re.search(r"obtido\s*=\s*([a-zA-Zçãáéíóú/]+)", avaliacao or "")
    if not match:
        return None
    for parte in re.split(r"[/|,]", match.group(1)):
        nivel = parte.strip().lower()
        if nivel in BLOOM_ORDER:
            return BLOOM_ORDER.index(nivel)
    return None


def correlacao_pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    media_x = sum(xs) / n
    media_y = sum(ys) / n
    cov = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    var_x = sum((x - media_x) ** 2 for x in xs)
    var_y = sum((y - media_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def coletar_pares(diretorio: str) -> list[tuple[int, int]]:
    """Devolve pares (tokens_da_resposta, indice_do_nivel_atribuido)."""
    import csv

    padrao = os.path.join(diretorio, "**", "skill_evaluator.csv")
    pares: list[tuple[int, int]] = []

    for caminho in glob.glob(padrao, recursive=True):
        with open(caminho, newline="", encoding="utf-8") as arquivo:
            for linha in csv.DictReader(arquivo):
                nivel = extrair_nivel(linha.get("avaliacao_valuator", ""))
                if nivel is None:
                    continue
                tokens = contar_tokens(linha.get("resposta", ""))
                if tokens == 0:
                    continue
                pares.append((tokens, nivel))

    return pares


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="artifacts/observability")
    parser.add_argument("--limiar", type=float, default=LIMIAR_PADRAO)
    parser.add_argument(
        "--minimo",
        type=int,
        default=MINIMO_DE_PARES,
        help="pares mínimos para o resultado ser interpretável",
    )
    args = parser.parse_args()

    pares = coletar_pares(args.dir)

    if not pares:
        print(f"Nenhum par encontrado em {args.dir}/**/skill_evaluator.csv")
        print("Aponte --dir para o diretório com os artefatos de observabilidade reais.")
        return 2

    tokens = [float(t) for t, _ in pares]
    niveis = [float(n) for _, n in pares]
    r = correlacao_pearson(tokens, niveis)

    print(f"Pares analisados:       {len(pares)}")
    print(f"Tokens (min/med/max):   {min(tokens):.0f} / {sum(tokens)/len(tokens):.1f} / {max(tokens):.0f}")
    print(f"Correlação r:           {r if r is None else f'{r:.3f}'}")
    print(f"Limiar de alerta:       {args.limiar}")

    if len(pares) < args.minimo:
        print()
        print(f"AMOSTRA INSUFICIENTE: {len(pares)} pares, mínimo {args.minimo}.")
        print("O número acima não sustenta conclusão nenhuma sobre viés.")
        return 2

    if r is None:
        print()
        print("SEM VARIÂNCIA: todas as respostas têm o mesmo tamanho ou o mesmo nível.")
        return 2

    print()
    if abs(r) > args.limiar:
        print(f"ALERTA VERMELHO: |r| = {abs(r):.3f} > {args.limiar}.")
        print("O nível atribuído acompanha o tamanho da resposta.")
        print("Ver spec §6.2: mitigações de viés de registro verbal.")
        return 1

    print(f"OK: |r| = {abs(r):.3f} dentro do limiar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
