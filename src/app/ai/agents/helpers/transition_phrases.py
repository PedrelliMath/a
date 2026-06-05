import random

TRANSITION_PHRASES: list[str] = [
    "Trazendo agora para outro ponto, ...",
    "Saindo desse tema e entrando em outro eixo, ...",
    "Avançando para uma nova frente, ...",
    "Passando agora para outro tema, ...",
    "Entrando em um novo bloco da conversa, ...",
    "Trazendo uma outra questão, ...",
    "Abrindo o próximo ponto, ...",
    "Seguindo para outro eixo de análise, ...",
    "Agora, olhando para outra frente, ...",
    "Avançando para o próximo bloco, ...",
    "Saindo desse recorte e indo para outro ponto, ...",
]


def pick_transition_phrase(used: list[str]) -> str:
    pool = [p for p in TRANSITION_PHRASES if p not in used] or TRANSITION_PHRASES
    return random.choice(pool)
