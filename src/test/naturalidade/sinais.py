"""Contadores da tabela de verificação de naturalidade.

Os sinais são os da seção "Verificação" do documento de refactor. Quatro deles
são objetivos e podem ser contados sozinhos; "referência concreta à resposta
anterior" é heurístico e serve para dirigir a leitura humana, não para
substituí-la.
"""
from __future__ import annotations

import re
import unicodedata

# Mesma lista do system_prompt do supervisor.
PALAVRAS_PROIBIDAS = [
    "bacana", "que interessante", "compreendo", "entendi seu ponto",
    "que legal", "otimo", "excelente", "muito bom",
    "vamos juntos", "podemos explorar juntos", "vamos aprofundar juntos",
    "sua visao e importante", "obrigado por compartilhar", "que reflexao profunda",
]

# Aberturas genéricas de transição (as 11 frases removidas no R5 e variantes).
ABERTURAS_GENERICAS = re.compile(
    r"^\s*(trazendo|saindo desse|avancando|passando (agora )?para|entrando em|"
    r"abrindo o proximo|seguindo para|agora,? olhando|mudando de|"
    r"vamos (agora )?(para|falar)|dando sequencia|prosseguindo)",
    re.IGNORECASE,
)

STOPWORDS = {
    "para", "como", "quando", "porque", "sobre", "entre", "aquele", "aquela",
    "voce", "sua", "seu", "isso", "essa", "esse", "mais", "menos", "pode",
    "pelo", "pela", "onde", "qual", "quais", "havia", "estava", "tinha",
    "descreva", "situacao", "exemplo", "conte", "explique",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def contar_frases(texto: str) -> int:
    partes = [p for p in re.split(r"(?<=[.!?])\s+", (texto or "").strip()) if p.strip()]
    return len(partes)


def palavras_de_conteudo(texto: str) -> set[str]:
    return {
        p for p in re.findall(r"[a-z]{5,}", normalizar(texto))
        if p not in STOPWORDS
    }


def avaliar_mensagem(
    mensagem: str,
    resposta_anterior: str | None = None,
    pergunta_gerada: str | None = None,
) -> dict:
    """Marca os cinco sinais para uma mensagem do supervisor."""
    normalizada = normalizar(mensagem)

    proibidas = [p for p in PALAVRAS_PROIBIDAS if p in normalizada]

    # Referência concreta: palavra de conteúdo que veio da resposta do
    # candidato e não da pergunta que o gerador entregou pronta.
    referencia = []
    if resposta_anterior:
        do_candidato = palavras_de_conteudo(resposta_anterior)
        da_pergunta = palavras_de_conteudo(pergunta_gerada or "")
        referencia = sorted(
            (palavras_de_conteudo(mensagem) & do_candidato) - da_pergunta
        )

    return {
        "perguntas_compostas": mensagem.count("?") >= 2,
        "abertura_generica": bool(ABERTURAS_GENERICAS.match(normalizada)),
        "referencia_concreta": bool(referencia),
        "referencia_termos": referencia,
        "palavras_proibidas": proibidas,
        "frases": contar_frases(mensagem),
    }


def tabela(resultados: list[dict], limite_frases: int = 2) -> str:
    """Renderiza a tabela de verificação a partir das mensagens marcadas."""
    total = len(resultados)
    linhas = [
        ("Mensagens com duas ou mais perguntas",
         sum(r["perguntas_compostas"] for r in resultados), "zero"),
        ("Mensagens que abrem com frase de transição genérica",
         sum(r["abertura_generica"] for r in resultados), "zero"),
        ("Mensagens que referenciam algo concreto da resposta anterior",
         sum(r["referencia_concreta"] for r in resultados), "pelo menos 3 em 5"),
        ("Uso de palavra da lista proibida",
         sum(bool(r["palavras_proibidas"]) for r in resultados), "zero"),
        (f"Mensagens acima de {limite_frases} frases",
         sum(r["frases"] > limite_frases for r in resultados), "zero"),
    ]
    largura = max(len(nome) for nome, _, _ in linhas)
    saida = [f"{'Sinal'.ljust(largura)} | valor | meta", f"{'-' * largura}-+-------+------"]
    for nome, valor, meta in linhas:
        saida.append(f"{nome.ljust(largura)} | {str(valor).rjust(5)} | {meta}")
    saida.append(f"\nmensagens do supervisor analisadas: {total}")
    return "\n".join(saida)
