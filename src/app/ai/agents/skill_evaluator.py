"""Skill Evaluator using fine-tuned model for bloom level classification."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import unicodedata
import pandas as pd

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)

OBSERVABILITY_DIR = os.getenv("SKILL_EVALUATOR_OBSERVABILITY_DIR", "artifacts/observability")


class SkillAnalysisItem(BaseModel):
    """Nível de Bloom observado para uma competência individual, em um turno.

    C1 (spec §15): este é o dado que o avaliador já produzia e que era descartado.
    A votação por maioria colapsa tudo isto em um int de -1 a 1; aqui o detalhe é preservado
    para persistir em `evaluations.iterations` e permitir reprocessamento sem LLM (P5).
    """
    skill: str
    expected_bloom_level: str | None = None
    achieved_bloom_level: str | None = None
    adequacao: int = Field(default=0, ge=-1, le=1)
    status: str = ""


class AgentSkillEvaluatorResponse(BaseModel):
    """Response model for skill evaluator"""
    classificacao: int = Field(description="intervalo", ge=-1, le=1)
    adequacao_habilidades: str = Field(description="avaliação detalhada por habilidade")
    adequacao_macro: str = Field(description="classificação macro")
    justificativas_habilidades: str = Field(
        default="",
        description="justificativas concatenadas por habilidade",
    )
    skill_analysis: list[SkillAnalysisItem] = Field(
        default_factory=list,
        description="nível observado por competência individual, preservado por turno",
    )


def _bloom_relation_label(value: int) -> str:
    return {
        -1: "inadequado",
        0: "adequado",
        1: "acima_do_esperado",
    }.get(value, "desconhecido")


def _safe_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("._-") or "assessment"


def _build_skill_valuator_summary(skill_analysis_item: dict[str, Any]) -> str:
    return (
        f"habilidade={skill_analysis_item.get('skill', '')}; "
        f"esperado={skill_analysis_item.get('expected_bloom_level', '')}; "
        f"obtido={skill_analysis_item.get('achieved_bloom_level', '')}; "
        f"adequacao={skill_analysis_item.get('adequacao', '')}; "
        f"status={skill_analysis_item.get('status', '')}"
    )


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def parse_evaluations(row):
        blocks = row['avaliacao_valuator'].split('|')
        
        results = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            parts = block.split(';')
            d = {}
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    d[k.strip()] = v.strip()
            results.append(d)
        return results


def _persist_skill_evaluator_artifacts(audit_payload: dict[str, Any]) -> None:
    session_id = audit_payload.get("session_id") or "assessment"
    assessment_dir = Path(OBSERVABILITY_DIR) / "skill_evaluator" / _safe_filename(str(session_id))
    assessment_dir.mkdir(parents=True, exist_ok=True)

    json_path = assessment_dir / "skill_evaluator_detail.json"
    csv_path = assessment_dir / "skill_evaluator.csv"
    csv_fieldnames = [
        "macro",
        "resposta",
        "avaliacao_valuator",
        "justificativas_habilidades",
        "avaliacao_humana",
    ]

    existing_payload = {
        "session_id": str(session_id),
        "iterations": [],
    }
    if json_path.exists():
        try:
            existing_payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            existing_payload = {"session_id": str(session_id), "iterations": []}

    iterations = existing_payload.get("iterations") if isinstance(existing_payload, dict) else []
    if not isinstance(iterations, list):
        iterations = []

    iterations.append(audit_payload)
    payload = {
        "session_id": str(session_id),
        "assessment_dir": str(assessment_dir),
        "total_iterations": len(iterations),
        "iterations": iterations,
    }

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    if csv_path.exists():
        try:
            existing_csv = pd.read_csv(csv_path)
            needs_rewrite = any(col not in existing_csv.columns for col in csv_fieldnames)
            if needs_rewrite:
                for col in csv_fieldnames:
                    if col not in existing_csv.columns:
                        existing_csv[col] = ""
                existing_csv = existing_csv[csv_fieldnames]
                existing_csv.to_csv(csv_path, index=False)
        except Exception as migration_error:
            logger.warning(
                f"Falha ao migrar schema do CSV de observabilidade: {migration_error}"
            )

    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        import csv

        writer = csv.DictWriter(
            csv_file,
            fieldnames=csv_fieldnames,
        )
        if write_header:
            writer.writeheader()

        skill_analysis = audit_payload.get("skill_analysis") or []
        if not skill_analysis:
            skill_analysis = [{
                "skill": audit_payload.get("macrocompetencia", ""),
                "expected_bloom_level": audit_payload.get("expected_bloom_level", ""),
                "achieved_bloom_level": audit_payload.get("parsed_achieved_levels", {}).get(
                    audit_payload.get("macrocompetencia", ""),
                    "",
                ),
                "adequacao": audit_payload.get("classification", ""),
                "status": audit_payload.get("adequacao_macro", ""),
            }]

        for skill_item in skill_analysis:
            writer.writerow(
                {
                    "macro": audit_payload.get("macrocompetencia", ""),
                    "resposta": audit_payload.get("response", ""),
                    "avaliacao_valuator": audit_payload.get(
                        "avaliacao_valuator",
                        _build_skill_valuator_summary(skill_item),
                    ),
                    "justificativas_habilidades": audit_payload.get(
                        "justificativas_habilidades",
                        "",
                    ),
                    "avaliacao_humana": audit_payload.get("avaliacao_humana", ""),
                }
            )

        csv = pd.read_csv(csv_path)
        csv.drop_duplicates().to_csv(csv_path, index=False)

        csv['eval_list'] = csv.apply(parse_evaluations, axis=1)
        df_exploded = csv.explode('eval_list').reset_index(drop=True)

        eval_df = pd.json_normalize(df_exploded['eval_list'])
        df_final = pd.concat([df_exploded.drop(columns=['avaliacao_valuator', 'eval_list']), eval_df], axis=1)
        df_final.to_csv(assessment_dir / "skill_evaluator_cleaned.csv", index=False)


def normalize_skill_name(skill_name: str) -> str:
    """
    Normalize skill name to snake_case format.

    Examples:
        "Dados e Inteligência Artificial" -> "dados_e_inteligencia_artificial"
        "Orientação a Serviços" -> "orientacao_a_servicos"
    """
    skill_name = unicodedata.normalize("NFD", skill_name)
    skill_name = "".join(
        char for char in skill_name if unicodedata.category(char) != "Mn"
    )
    skill_name = skill_name.lower().strip()
    skill_name = re.sub(r"\s+", "_", skill_name)
    return skill_name


def parse_skill_group(skill_group: str) -> list[str]:
    """
    Parse a comma-separated skill group into individual skills.

    Examples:
        "Dados e IA, Solução de Problemas" ->
        ["dados_e_ia", "solucao_de_problemas"]
    """
    skills = [s.strip() for s in skill_group.split(",")]
    return [normalize_skill_name(s) for s in skills]


BLOOM_ORDER = [
    "lembrar",
    "compreender",
    "aplicar",
    "analisar",
    "avaliar",
    "criar",
]


def _parse_achieved_levels(achieved: str) -> list[str]:
    """Parse achieved bloom levels, supporting formats like 'avaliar/criar'."""
    if not achieved:
        return []
    candidates = [p.strip().lower() for p in re.split(r"[/|,]", achieved) if p.strip()]
    return [c for c in candidates if c in BLOOM_ORDER]


def compare_bloom_levels(expected: str, achieved: str) -> int:
    """
    Compare two bloom level strings and return adequacao:
      -1 -> achieved is below expected
       0 -> achieved equals expected
       1 -> achieved is above expected
    """
    try:
        exp_idx = BLOOM_ORDER.index(expected.lower())
    except ValueError:
        return 0

    achieved_levels = _parse_achieved_levels(achieved)
    if not achieved_levels:
        return 0

    achieved_indexes = [BLOOM_ORDER.index(level) for level in achieved_levels]
    ach_idx = min(achieved_indexes, key=lambda idx: abs(idx - exp_idx))

    if ach_idx < exp_idx:
        return -1
    if ach_idx == exp_idx:
        return 0
    return 1


class AgentSkillEvaluator:
    """Skill evaluator using fine-tuned OpenAI model"""

    def __init__(
        self,
        model_id: str,
        system_prompt_template: str,
        justification_prompt_template: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        justification_model_id: str = "gpt-4o-mini",
    ):
        self.model_id = model_id
        self.system_prompt_template = system_prompt_template
        self.justification_prompt_template = justification_prompt_template
        self.temperature = temperature
        self.justification_model_id = justification_model_id
        
        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**client_kwargs)

        logger.info(f"SkillEvaluator initialized with model: {model_id}")

    def _normalize_two_line_justification(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        if not cleaned:
            return "Sem justificativa disponível."

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) >= 2:
            return f"{sentences[0]}\n{sentences[1]}"
        return cleaned

    def _build_justification_output(
        self,
        individual_skills: list[str],
        achieved_levels: dict[str, str],
        justifications: dict[str, str],
    ) -> str:
        parts = []
        for skill in individual_skills:
            bloom_level = achieved_levels.get(skill) or "na"
            justification = self._normalize_two_line_justification(
                justifications.get(skill) or "Sem justificativa disponível."
            )
            parts.append(
                "{"
                f"{skill}:{bloom_level}, "
                f"justificativa:{justification}"
                "}"
            )
        return "; ".join(parts)

    @track_helicone(agent_type="skill_evaluator")
    async def run_evaluation(self, evaluation_context: dict) -> AgentSkillEvaluatorResponse:
        """
        Evaluate user response and classify bloom level.

        Args:
            evaluation_context: Dict containing:
                - user_message: User's response
                - current_proficiency_level: Expected bloom level
                - bloom_levels: Dict with level descriptions
                - rubrics: Dict with questions per skill/level
                - current_specific_skill: Current skill group being evaluated
                - question: Current question asked
                - session (optional): Session object with id

        Returns:
            AgentSkillEvaluatorResponse with classification, adequacao_habilidades and adequacao_macro
        """
        logger.info("=" * 80)
        logger.info("🎯 SKILL EVALUATOR - INICIANDO AVALIAÇÃO")
        logger.info("=" * 80)

        resposta_usuario = evaluation_context["user_message"]
        nivel_esperado = evaluation_context["current_proficiency_level"]
        current_skill_group = evaluation_context["current_specific_skill"]

        logger.info(f"Nível esperado: {nivel_esperado}")
        logger.info(f"Macrocompetência: {current_skill_group}")
        logger.info(f"Resposta do usuário (preview): {resposta_usuario[:100]}...")
        question = evaluation_context.get("question", "")
        
        # Parse skill group into individual skills

        individual_skills = parse_skill_group(current_skill_group)

        # C2 (spec §15): o enunciado passa a integrar o payload de classificação.
        # Sem ele o avaliador julga a resposta no vácuo e resposta fora do tópico pontua alto.
        dados_classificacao = {
            "habilidades_macro": individual_skills,
            "pergunta": question,
        }

        logger.info("📋 Dados de classificação:")
        logger.info(json.dumps(dados_classificacao, ensure_ascii=False, indent=2))
        
        # Execute inference
        conteudo, system_message = await self._executar_inferencia(
            resposta_usuario=resposta_usuario,
            dados_classificacao=dados_classificacao,
        )

        achieved_levels, _raw_output = self._parse_response(conteudo)

        # Compute adequacao per skill by comparing achieved vs expected
        adequacoes = {}
        skill_analysis = []
        for skill in individual_skills:
            achieved = achieved_levels.get(skill)
            adequ = compare_bloom_levels(nivel_esperado, achieved or "") if achieved else 0
            adequacoes[skill] = adequ
            skill_analysis.append(
                {
                    "skill": skill,
                    "expected_bloom_level": nivel_esperado,
                    "achieved_bloom_level": achieved,
                    "adequacao": adequ,
                    "status": _bloom_relation_label(adequ),
                }
            )

        inadequacoes = [item for item in skill_analysis if item["adequacao"] != 0]

        adequacao_habilidades = ", ".join([f"{k}:{v}" for k, v in adequacoes.items()])

        justificativas = await self._generate_skill_justifications(
            user_message=resposta_usuario,
            skill_analysis=skill_analysis,
        )
        justificativas_habilidades = self._build_justification_output(
            individual_skills=individual_skills,
            achieved_levels=achieved_levels,
            justifications=justificativas,
        )

        # Determine adequacao_macro by majority vote over adequacoes values
        if adequacoes:
            counts: dict[int, int] = {-1: 0, 0: 0, 1: 0}
            for v in adequacoes.values():
                counts[v] = counts.get(v, 0) + 1
            max_count = max(counts.values())
            winners = [k for k, v in counts.items() if v == max_count]
            if 0 in winners:
                macro_vote = 0
            elif -1 in winners:
                macro_vote = -1
            else:
                macro_vote = 1

            adequacao_macro = str(macro_vote)
            classificacao = int(adequacao_macro)
        else:
            adequacao_macro = "0"
            classificacao = 0

        logger.info("=" * 80)
        logger.info("🎯 SKILL EVALUATOR - RESULTADO FINAL")
        logger.info(f"Classificação: {classificacao} ('-1=Abaixo, 0=Igual, 1=Acima')")
        logger.info(f"Adequação Macro: {adequacao_macro}")
        logger.info(f"Adequação Habilidades: {adequacao_habilidades}")
        logger.info(f"Justificativas Habilidades: {justificativas_habilidades}")
        logger.info("=" * 80)
        # Log model id and session info for debugging finetune evaluation

        # FIX #10: indentação corrigida (estava fora do bloco acidentalmente)
        logger.info(f"Model usado para avaliação finetune: {self.model_id}")

        session_obj = (
            evaluation_context.get("session")
            if isinstance(evaluation_context, dict)
            else None
        )
        session_id = None
        if session_obj:
            if isinstance(session_obj, dict):
                session_id = session_obj.get("id") or session_obj.get("session_id")
            else:
                session_id = getattr(session_obj, "id", None) or getattr(
                    session_obj, "session_id", None
                )
        if session_id:
            logger.info(f"Session ID: {session_id}")

        avaliacao_valuator = " | ".join(
            _build_skill_valuator_summary(item) for item in skill_analysis
        )

        audit_payload = {
            "question": question,
            "response": resposta_usuario,
            "expected_bloom_level": nivel_esperado,
            "macrocompetencia": current_skill_group,
            "individual_skills": individual_skills,
            "dados_classificacao": dados_classificacao,
            "system_prompt": system_message,
            "raw_response": conteudo,
            "parsed_achieved_levels": achieved_levels,
            "skill_analysis": skill_analysis,
            "adequacoes": adequacoes,
            "inadequacoes": inadequacoes,
            "adequacao_habilidades": adequacao_habilidades,
            "justificativas_habilidades": justificativas_habilidades,
            "justificativas_map": justificativas,
            "adequacao_macro": adequacao_macro,
            "classification": classificacao,
            "avaliacao_valuator": avaliacao_valuator,
            "model_id": self.model_id,
            "temperature": self.temperature,
            "justification_model_id": self.justification_model_id,
            "session_id": session_id,
        }

        try:
            _persist_skill_evaluator_artifacts(audit_payload)
        except Exception as export_error:
            logger.warning(f"Falha ao persistir artefatos do skill evaluator: {export_error}")

        # Return structured response (mimicking pydantic_ai output structure)
        class Output:
            def __init__(self, data: AgentSkillEvaluatorResponse, audit_payload: dict):
                self.output = data
                self.audit_payload = audit_payload
        
        return Output(AgentSkillEvaluatorResponse(
            classificacao=classificacao,
            adequacao_habilidades=adequacao_habilidades,
            adequacao_macro=adequacao_macro,
            justificativas_habilidades=justificativas_habilidades,
            skill_analysis=[SkillAnalysisItem(**item) for item in skill_analysis],
        ), audit_payload)

    async def _generate_skill_justifications(
        self,
        user_message: str,
        skill_analysis: list[dict[str, Any]],
    ) -> dict[str, str]:
        skills_with_bloom = [
            {
                "habilidade": item.get("skill", ""),
                "avaliacao_bloom": item.get("achieved_bloom_level", ""),
                "adequacao": item.get("adequacao", 0),
            }
            for item in skill_analysis
        ]

        payload = {
            "user_message": user_message,
            "skills": skills_with_bloom,
        }

        system_message = self.justification_prompt_template

        try:
            completion = await self.client.chat.completions.create(
                model=self.justification_model_id,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            raw_response = completion.choices[0].message.content or "{}"
            parsed = json.loads(raw_response)
            items = parsed.get("justificativas", []) if isinstance(parsed, dict) else []

            mapping: dict[str, str] = {}
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    skill = normalize_skill_name(str(item.get("habilidade", "")).strip())
                    justification = str(item.get("justificativa", "")).strip()
                    if skill and justification:
                        mapping[skill] = justification

            return mapping
        except Exception as exc:
            logger.warning(f"Falha ao gerar justificativas por habilidade: {exc}")
            return {}

    async def _executar_inferencia(
        self,
        resposta_usuario: str,
        dados_classificacao: Dict[str, Any],
    ) -> tuple[str, str]:
        """
        Execute inference using fine-tuned model.
        
        Args:
            resposta_usuario: User's response
            dados_classificacao: Classification data dict
            
        Returns:
            Model response as string
        """
        if not resposta_usuario.strip():
            raise ValueError("resposta_usuario cannot be empty")

        system_message = self.system_prompt_template.format(
            dados_classificacao=json.dumps(dados_classificacao, ensure_ascii=False)
        )

        logger.info("📝 SYSTEM PROMPT:")
        logger.info(system_message)
        logger.info("")
        logger.info("💬 USER MESSAGE:")
        logger.info(resposta_usuario)
        logger.info("")
        logger.info(f"🤖 Chamando modelo fine-tuned (temperature={self.temperature})...")

        completion = await self.client.chat.completions.create(
            model=self.model_id,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": resposta_usuario.strip()},
            ],
        )

        raw_response = completion.choices[0].message.content or ""

        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 RESPOSTA BRUTA DO MODELO FINE-TUNED:")
        logger.info("=" * 80)
        logger.info(raw_response)
        logger.info("=" * 80)
        
        return raw_response, system_message

    def _parse_response(self, response: str) -> tuple[dict, str]:
        """
        Parse model response to extract achieved bloom levels per skill.

        Expected model JSON:
        {"habilidades": {"colaboracao": "analisar", "empatia": "avaliar"}}

        Returns:
            Tuple of (achieved_levels_dict, raw_response_str)
        """
        logger.info(f"📊 Parsing SkillEvaluator response: {response[:200]}...")

        achieved_levels: dict = {}

        try:
            data = json.loads(response)

            if isinstance(data, dict) and "habilidades" in data:
                hab = data["habilidades"]
                if isinstance(hab, dict):
                    for k, v in hab.items():
                        achieved_levels[normalize_skill_name(k)] = str(v)
                elif isinstance(hab, str):
                    parts = [p.strip() for p in hab.split(",") if p.strip()]
                    for p in parts:
                        if ":" in p:
                            key, val = p.split(":", 1)
                            achieved_levels[normalize_skill_name(key)] = val.strip()

            elif isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str):
                        achieved_levels[normalize_skill_name(k)] = v

        except json.JSONDecodeError:
            logger.debug("Resposta não é JSON, tentando parse heurístico...")

        if not achieved_levels and isinstance(response, str):
            parts = [p.strip() for p in re.split(r",|;|\n", response) if p.strip()]
            for p in parts:
                if ":" in p:
                    key, val = p.split(":", 1)
                    achieved_levels[normalize_skill_name(key)] = val.strip()

        logger.info(f"✅ Achieved levels parsed: {achieved_levels}")

        return achieved_levels, response.strip()