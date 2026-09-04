"""Roda N sessões completas e conta os sinais da tabela de verificação.

O documento de refactor pede 5 sessões manuais depois de cada bloco, com os
números anotados. Este script automatiza a parte mecânica: conduz as sessões
contra os modelos de verdade e conta os sinais. Ele NÃO substitui a leitura
humana — em particular o sinal "referência concreta" é heurístico, e as
transcrições ficam gravadas para conferência.

Uso:

    export OPENAI_API_KEY=...
    # com o banco de perguntas vindo do Postgres (caminho realista)
    python src/test/naturalidade/run_sessions.py --skill-id <uuid> --sessions 5

    # ou com um arquivo de rubricas, sem depender do banco
    python src/test/naturalidade/run_sessions.py --skill-json rubricas.json

O JSON de rubricas tem o mesmo formato de `skills.questions`:

    {"rubrics": {"macro": {"analisar": ["pergunta de referência", ...]}},
     "bloom_levels": {"analisar": 4}}

Por padrão o skill_evaluator é dublado (ele depende do modelo fine-tuned e não
influencia a naturalidade do texto). Use --real-evaluator para incluí-lo.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import types
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic_ai import Agent  # noqa: E402

from sinais import avaliar_mensagem, tabela  # noqa: E402

PERSONAS = [
    "Você é uma pessoa candidata objetiva, com 8 anos de experiência em dados. "
    "Responde em 2 a 4 frases, com exemplos concretos do trabalho.",
    "Você é uma pessoa candidata prolixa, que se perde em contexto antes de "
    "chegar ao ponto. Responde em 5 a 7 frases.",
    "Você é uma pessoa candidata júnior e insegura. Responde curto, às vezes "
    "sem exemplo concreto, e às vezes pede para repetir a pergunta.",
    "Você é uma pessoa candidata sênior e impaciente. Responde em 1 ou 2 "
    "frases diretas e ocasionalmente questiona a pergunta.",
    "Você é uma pessoa candidata que às vezes muda de assunto e comenta algo "
    "fora do escopo antes de responder.",
]

STUB_EVALUATION = {
    "classificacao": 0,
    "adequacao_habilidades": "",
    "adequacao_macro": "adequado",
    "justificativas_habilidades": "",
}


class SessaoFalsa:
    """Session duck-typed: o orquestrador só precisa de id, user_id e skill."""

    def __init__(self, skill, user_id: str):
        self.id = f"naturalidade-{user_id}"
        self.user_id = user_id
        self.skill = skill
        self.messages: list[dict] = []
        self.model_messages: list = []

    def to_dict(self, include_messages: bool = False) -> dict:
        return {"messages": self.messages, "model_messages": self.model_messages}


def carregar_skill(args) -> types.SimpleNamespace:
    if args.skill_json:
        questions = json.loads(Path(args.skill_json).read_text(encoding="utf-8"))
        return types.SimpleNamespace(
            name=args.skill_name, questions=questions, agents_config={}
        )

    from app.database.db import SessionLocal
    from app.models.skill import Skill

    db = SessionLocal()
    try:
        skill = db.query(Skill).filter(Skill.id == args.skill_id).first()
        if not skill:
            raise SystemExit(f"skill {args.skill_id} não encontrada")
        return types.SimpleNamespace(
            name=skill.name,
            questions=skill.questions,
            agents_config=skill.agents_config or {},
        )
    finally:
        db.close()


async def rodar_sessao(skill, persona: str, turnos: int, modelo_candidato: str,
                       real_evaluator: bool, indice: int) -> list[dict]:
    from app.ai.agents.services.agent_orquestrator import create_agent_orquestrator

    candidato = Agent(model=modelo_candidato, output_type=str, instructions=persona)
    sessao = SessaoFalsa(skill, f"candidato-{indice}")
    transcricao: list[dict] = []

    async def responder() -> str:
        conversa = "\n".join(f"{m['user_type']}: {m['text']}" for m in sessao.messages)
        resultado = await candidato.run(
            f"Conversa até aqui:\n{conversa}\n\nResponda à última mensagem."
        )
        return resultado.output

    mensagem_usuario = None
    for turno in range(turnos + 1):
        orquestrador = create_agent_orquestrator(sessao, user_name=f"Candidato {indice}")
        await orquestrador._init_agents()

        if not real_evaluator:
            async def avaliacao_dublada(_contexto):
                return types.SimpleNamespace(
                    output=types.SimpleNamespace(**STUB_EVALUATION)
                )
            orquestrador.agent_skill_evaluator.run_evaluation = avaliacao_dublada

        saida = await orquestrador.get_response(mensagem_usuario)
        if not saida.supervisor_message:
            break

        pergunta = (saida.params.get("question_generator") or {}).get("question")
        transcricao.append({
            "turno": turno,
            "resposta_anterior": mensagem_usuario,
            "pergunta_gerada": pergunta,
            "supervisor": saida.supervisor_message,
            "acao": (saida.params.get("supervisor") or {}).get("action"),
        })

        sessao.messages = sessao.messages + [{
            "user_type": "bot", "text": saida.supervisor_message, "params": saida.params,
        }]
        if saida.model_messages is not None:
            sessao.model_messages = saida.model_messages

        if (saida.params.get("supervisor") or {}).get("action") == "close":
            break

        mensagem_usuario = await responder()
        sessao.messages = sessao.messages + [
            {"user_type": "user", "text": mensagem_usuario, "params": {}}
        ]

    return transcricao


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=5)
    parser.add_argument("--turns", type=int, default=6, help="turnos por sessão")
    parser.add_argument("--skill-id", help="uuid da skill no Postgres")
    parser.add_argument("--skill-json", help="arquivo com o mesmo formato de skills.questions")
    parser.add_argument("--skill-name", default="Skill de teste")
    parser.add_argument("--candidate-model", default="openai:gpt-4o-mini")
    parser.add_argument("--real-evaluator", action="store_true")
    parser.add_argument("--out", default="artifacts/naturalidade")
    args = parser.parse_args()

    if not args.skill_id and not args.skill_json:
        raise SystemExit("informe --skill-id ou --skill-json")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY não está definida")

    skill = carregar_skill(args)

    marcados: list[dict] = []
    transcricoes: list[list[dict]] = []
    for i in range(args.sessions):
        persona = PERSONAS[i % len(PERSONAS)]
        print(f"sessão {i + 1}/{args.sessions}...", flush=True)
        transcricao = await rodar_sessao(
            skill, persona, args.turns, args.candidate_model, args.real_evaluator, i
        )
        transcricoes.append(transcricao)
        for item in transcricao:
            # Saudação e fechamento têm exceção de formato declarada no prompt.
            if item["acao"] in ("greeting", "close"):
                continue
            marcados.append(avaliar_mensagem(
                item["supervisor"], item["resposta_anterior"], item["pergunta_gerada"]
            ))

    destino = Path(args.out)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"sessoes-{datetime.now():%Y%m%d-%H%M%S}.json"
    arquivo.write_text(
        json.dumps(transcricoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(tabela(marcados))
    print(f"\ntranscrições: {arquivo}")
    print("Confira à mão o sinal de referência concreta e a repetição de "
          "estrutura entre turnos: os dois pedem leitura humana.")


if __name__ == "__main__":
    asyncio.run(main())
