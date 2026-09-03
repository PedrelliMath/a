#!/usr/bin/env python3
"""Verifica a cobertura do banco de perguntas por célula (bloco × nível de Bloom).

Spec §4.1 e C6. Uma célula com menos de 3 itens quebra skip e reformulação: não há
de onde tirar uma pergunta diferente, e o sistema força troca de nível indevida só
para ter o que perguntar — o que corrompe a medição.

Este script é o precursor de `bank/validate.py` (spec §13). Enquanto o item bank v2 não
existe, ele valida a estrutura atual (`skill.questions.rubrics`).

Uso:
    python scripts/validate_question_bank.py updateskill.json
    python scripts/validate_question_bank.py updateskill.json --minimo 2
"""

from __future__ import annotations

import argparse
import json
import sys

BLOOM_ORDER = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]
MINIMO_POR_CELULA = 3


def carregar_rubrics(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    rubrics = (dados.get("questions") or {}).get("rubrics")
    if not isinstance(rubrics, dict) or not rubrics:
        raise SystemExit(f"{caminho}: `questions.rubrics` ausente ou vazio.")
    return rubrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", nargs="?", default="updateskill.json")
    parser.add_argument("--minimo", type=int, default=MINIMO_POR_CELULA)
    args = parser.parse_args()

    rubrics = carregar_rubrics(args.arquivo)

    faltantes: list[tuple[str, str, int]] = []
    ausentes: list[tuple[str, str]] = []
    total_itens = 0

    print(f"Banco: {args.arquivo}")
    print(f"Mínimo exigido por célula: {args.minimo}\n")

    for bloco, niveis in rubrics.items():
        linha = []
        for nivel in BLOOM_ORDER:
            itens = (niveis or {}).get(nivel)
            if itens is None:
                ausentes.append((bloco, nivel))
                linha.append(f"{nivel[:4]}=--")
                continue
            quantidade = len(itens)
            total_itens += quantidade
            if quantidade < args.minimo:
                faltantes.append((bloco, nivel, quantidade))
            linha.append(f"{nivel[:4]}={quantidade}")
        print(f"  {bloco}")
        print(f"    {'  '.join(linha)}")

    celulas = len(rubrics) * len(BLOOM_ORDER)
    print()
    print(f"Blocos: {len(rubrics)}   Células: {celulas}   Itens: {total_itens}")

    if ausentes:
        print(f"\nCélulas inexistentes ({len(ausentes)}):")
        for bloco, nivel in ausentes:
            print(f"  - {bloco} / {nivel}")

    if faltantes:
        print(f"\nCélulas abaixo do mínimo ({len(faltantes)}):")
        for bloco, nivel, quantidade in faltantes:
            print(f"  - {bloco} / {nivel}: {quantidade} item(ns), faltam {args.minimo - quantidade}")
        print()
        print("Skip e reformulação nessas células não têm item alternativo para oferecer.")
        print("Autoria de item é decisão de conteúdo do time: o item é o instrumento de medição.")
        return 1

    if ausentes:
        return 1

    print("\nOK: toda célula tem ao menos o mínimo de itens.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
