"""C1 (spec §15): o nível por competência precisa sobreviver até `evaluations.iterations`.

Antes destas mudanças o `skill_analysis` existia só em CSV local, em `artifacts/`, e era
perdido a cada deploy. O teste trava a regressão.
"""

from types import SimpleNamespace

from app.services.evaluation import EvaluationService

SKILL_ANALYSIS = [
    {
        "skill": "colaboracao",
        "expected_bloom_level": "analisar",
        "achieved_bloom_level": "avaliar",
        "adequacao": 1,
        "status": "acima_do_esperado",
    },
    {
        "skill": "empatia",
        "expected_bloom_level": "analisar",
        "achieved_bloom_level": "aplicar",
        "adequacao": -1,
        "status": "inadequado",
    },
]


def _service() -> EvaluationService:
    return EvaluationService(None, None, None)


def _bot(text, params):
    return {"user_type": "bot", "text": text, "params": params}


def _user(text):
    return {"user_type": "user", "text": text, "params": {}}


def _sessao(messages):
    return SimpleNamespace(messages=messages)


def test_skill_analysis_chega_nas_iterations():
    sessao = _sessao([
        _bot("Pergunta 1", {
            "supervisor": {"action": "greeting"},
            "new_proficiency_level": "analisar",
            "new_specific_skill": "Colaboração, Empatia",
        }),
        _user("Uma resposta com conteúdo."),
        _bot("Pergunta 2", {
            "message_validator": {"is_valid": True},
            "skill_evaluator": {
                "achieved_level": "avaliar",
                "skill_analysis": SKILL_ANALYSIS,
            },
            "new_proficiency_level": "avaliar",
            "new_specific_skill": "Colaboração, Empatia",
        }),
    ])

    iterations = _service()._extract_iterations_from_session(sessao)

    assert len(iterations) == 1
    assert iterations[0]["skill_analysis"] == SKILL_ANALYSIS
    assert [i["skill"] for i in iterations[0]["skill_analysis"]] == ["colaboracao", "empatia"]


def test_turno_pulado_nao_carrega_evidencia():
    sessao = _sessao([
        _bot("Pergunta 1", {
            "supervisor": {"action": "greeting"},
            "new_proficiency_level": "analisar",
            "new_specific_skill": "Autoconhecimento",
        }),
        _user("pular"),
        _bot("Pergunta 2", {
            "flow": {"type": "skip"},
            "new_proficiency_level": "analisar",
            "new_specific_skill": "Autoconhecimento",
        }),
    ])

    iterations = _service()._extract_iterations_from_session(sessao)

    assert iterations[0]["skipped"] is True
    assert iterations[0]["skill_analysis"] == []
    assert iterations[0]["achieved_bloom_level"] is None


def test_sessao_sem_skill_analysis_nao_quebra():
    """Sessões anteriores a esta mudança não têm o campo. Não podem estourar."""
    sessao = _sessao([
        _bot("Pergunta 1", {
            "supervisor": {"action": "greeting"},
            "new_proficiency_level": "analisar",
            "new_specific_skill": "Autoconhecimento",
        }),
        _user("Resposta."),
        _bot("Pergunta 2", {
            "message_validator": {"is_valid": True},
            "skill_evaluator": {"achieved_level": "aplicar"},
            "new_proficiency_level": "aplicar",
            "new_specific_skill": "Autoconhecimento",
        }),
    ])

    iterations = _service()._extract_iterations_from_session(sessao)

    assert iterations[0]["skill_analysis"] == []
    assert iterations[0]["achieved_bloom_level"] == "aplicar"
