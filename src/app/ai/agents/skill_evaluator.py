"""Skill Evaluator using fine-tuned model for bloom level classification."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional
import unicodedata

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.logger import get_log
from app.observability import track_helicone

logger = get_log(__name__)


class AgentSkillEvaluatorResponse(BaseModel):
    """Response model for skill evaluator"""
    classificacao: int = Field(description="intervalo", ge=-1, le=1)
    adequacao_habilidades: str = Field(description="avaliação detalhada por habilidade")
    adequacao_macro: str = Field(description="classificação macro")


def normalize_skill_name(skill_name: str) -> str:
    """
    Normalize skill name to snake_case format.
    
    Examples:
        "Dados e Inteligência Artificial" -> "dados_e_inteligencia_artificial"
        "Orientação a Serviços" -> "orientacao_a_servicos"
    """
    # Remove accents
    skill_name = unicodedata.normalize('NFD', skill_name)
    skill_name = ''.join(char for char in skill_name if unicodedata.category(char) != 'Mn')
    
    # Convert to lowercase and replace spaces with underscores
    skill_name = skill_name.lower().strip()
    skill_name = re.sub(r'\s+', '_', skill_name)
    
    return skill_name


def parse_skill_group(skill_group: str) -> list[str]:
    """
    Parse a comma-separated skill group into individual skills.
    
    Examples:
        "Dados e IA, Solução de Problemas" -> 
        ["dados_e_ia", "solucao_de_problemas"]
    """
    skills = [s.strip() for s in skill_group.split(',')]
    return [normalize_skill_name(s) for s in skills]


# Bloom levels ordered from lowest to highest
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

    If level not recognized, assume equal (0).
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
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
    ):
        """
        Initialize skill evaluator.
        
        Args:
            model_id: Fine-tuned model ID (e.g., "ft:gpt-4o-mini-2024-07-18:...")
            system_prompt_template: Template for system prompt
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional base URL for OpenAI API (e.g., Helicone proxy)
            temperature: Temperature for model inference (default: 0.0 for deterministic)
        """
        self.model_id = model_id
        self.system_prompt_template = system_prompt_template
        self.temperature = temperature
        
        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            
        self.client = AsyncOpenAI(**client_kwargs)
        
        logger.info(f"SkillEvaluator initialized with model: {model_id}")

    @track_helicone(agent_type="skill_evaluator")
    async def run_evaluation(self, evaluation_context: dict) -> AgentSkillEvaluatorResponse:
        """
        Evaluate user response and classify bloom level.
        
        Expected output from fine-tuned model:
        {
            "adequacao_habilidades": "skill1:-1, skill2:0, skill3:1",
            "adequacao_macro": "-1"
        }
        
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
        
        # Extract required data from context
        resposta_usuario = evaluation_context["user_message"]
        nivel_esperado = evaluation_context["current_proficiency_level"]
        current_skill_group = evaluation_context["current_specific_skill"]
        
        logger.info(f"Nível esperado: {nivel_esperado}")
        logger.info(f"Macrocompetência: {current_skill_group}")
        logger.info(f"Resposta do usuário (preview): {resposta_usuario[:100]}...")
        
        # Parse skill group into individual skills
        individual_skills = parse_skill_group(current_skill_group)
        
        # Build dados_classificacao in new format
        dados_classificacao = {
            "habilidades_macro": individual_skills,
        }
        
        logger.info("📋 Dados de classificação:")
        logger.info(json.dumps(dados_classificacao, ensure_ascii=False, indent=2))
        
        # Execute inference
        conteudo = await self._executar_inferencia(
            resposta_usuario=resposta_usuario,
            dados_classificacao=dados_classificacao
        )
        
        # Parse response to extract achieved bloom levels per skill
        achieved_levels, _raw_output = self._parse_response(conteudo)

        # Compute adequacao per skill by comparing achieved vs expected
        adequacoes = {}
        for skill, achieved in achieved_levels.items():
            adequ = compare_bloom_levels(nivel_esperado, achieved)
            adequacoes[skill] = adequ

        # Build adequacao_habilidades string
        adequacao_habilidades = ", ".join([f"{k}:{v}" for k, v in adequacoes.items()])

        # Determine adequacao_macro by majority vote over adequacoes values
        if adequacoes:
            counts = { -1: 0, 0: 0, 1: 0 }
            for v in adequacoes.values():
                counts[v] = counts.get(v, 0) + 1
            # pick the sign with highest count (ties: prefer 0, then 1, then -1)
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
        logger.info(f"Classificação: {classificacao} ({'-1=Abaixo, 0=Igual, 1=Acima'})")
        logger.info(f"Adequação Macro: {adequacao_macro}")
        logger.info(f"Adequação Habilidades: {adequacao_habilidades}")
        logger.info("=" * 80)
        
            # Log model id and session info for debugging finetune evaluation
        logger.info(f"Model usado para avaliação finetune: {self.model_id}")
        session_obj = evaluation_context.get("session") if isinstance(evaluation_context, dict) else None
        session_id = None
        if session_obj:
            if isinstance(session_obj, dict):
                session_id = session_obj.get("id") or session_obj.get("session_id")
            else:
                session_id = getattr(session_obj, "id", None) or getattr(session_obj, "session_id", None)
        if session_id:
            logger.info(f"Session ID: {session_id}")
        # Return structured response (mimicking pydantic_ai output structure)
        class Output:
            def __init__(self, data: AgentSkillEvaluatorResponse):
                self.output = data
        
        return Output(AgentSkillEvaluatorResponse(
            classificacao=classificacao,
            adequacao_habilidades=adequacao_habilidades,
            adequacao_macro=adequacao_macro
        ))

    async def _executar_inferencia(
        self,
        resposta_usuario: str,
        dados_classificacao: Dict[str, Any],
    ) -> str:
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
        
        return raw_response

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

        # Try to parse as JSON first
        try:
            data = json.loads(response)

            # If model returned top-level 'habilidades' dict
            if isinstance(data, dict) and "habilidades" in data:
                hab = data["habilidades"]
                if isinstance(hab, dict):
                    for k, v in hab.items():
                        achieved_levels[normalize_skill_name(k)] = str(v)
                elif isinstance(hab, str):
                    # fallback to parsing string
                    raw = hab
                    parts = [p.strip() for p in raw.split(',') if p.strip()]
                    for p in parts:
                        if ':' in p:
                            key, val = p.split(':', 1)
                            achieved_levels[normalize_skill_name(key)] = val.strip()

            # Otherwise, if the JSON itself is a mapping of skills -> levels
            elif isinstance(data, dict):
                # try to interpret keys as skills
                for k, v in data.items():
                    if isinstance(v, str):
                        achieved_levels[normalize_skill_name(k)] = v

        except json.JSONDecodeError:
            logger.debug("Resposta não é JSON, tentando parse heurístico...")

        # Heuristic: try to parse patterns like 'colaboracao:analisar, empatia:avaliar'
        if not achieved_levels and isinstance(response, str):
            parts = [p.strip() for p in re.split(r',|;|\n', response) if p.strip()]
            for p in parts:
                if ':' in p:
                    key, val = p.split(':', 1)
                    achieved_levels[normalize_skill_name(key)] = val.strip()

        logger.info(f"✅ Achieved levels parsed: {achieved_levels}")

        return achieved_levels, response.strip()
