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
    justificativa: str = Field(description="breve explicação")


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


class AgentSkillEvaluator:
    """Skill evaluator using fine-tuned OpenAI model"""
    
    def __init__(
        self,
        model_id: str,
        system_prompt_template: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize skill evaluator.
        
        Args:
            model_id: Fine-tuned model ID (e.g., "ft:gpt-4o-mini-2024-07-18:...")
            system_prompt_template: Template for system prompt
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional base URL for OpenAI API (e.g., Helicone proxy)
        """
        self.model_id = model_id
        self.system_prompt_template = system_prompt_template
        
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
        
        New format for fine-tuned model. Expected output:
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
            AgentSkillEvaluatorResponse with classification and justification
        """
        # Extract required data from context
        resposta_usuario = evaluation_context["user_message"]
        nivel_esperado = evaluation_context["current_proficiency_level"]
        current_skill_group = evaluation_context["current_specific_skill"]
        
        # Get description for expected level
        descricao_nivel_esperado = evaluation_context["bloom_levels"][nivel_esperado]["descricao"]
        
        # Get the question
        pergunta_aferidora = evaluation_context.get("question", "")
        if not pergunta_aferidora and "rubrics" in evaluation_context:
            # Fallback: get first question from rubrics
            rubrics = evaluation_context["rubrics"]
            if current_skill_group in rubrics:
                questions = rubrics[current_skill_group].get(nivel_esperado, [])
                if questions and isinstance(questions, list):
                    pergunta_aferidora = questions[0]
        
        # Parse skill group into individual skills
        individual_skills = parse_skill_group(current_skill_group)
        
        # Build habilidades_macro dict - all skills start at the same level
        habilidades_macro = {
            skill: nivel_esperado for skill in individual_skills
        }
        
        # Get session ID if available
        session = evaluation_context.get("session")
        registro_id = str(session.id) if session else "unknown"
        
        # Build dados_classificacao in new format
        dados_classificacao = {
            "nivel_esperado": nivel_esperado,
            "descricao_nivel_esperado": descricao_nivel_esperado,
            "pergunta_aferidora": pergunta_aferidora,
            "habilidades_macro": habilidades_macro,
            "nome_grupo": normalize_skill_name(current_skill_group),
            "nome_habilidade": individual_skills[0] if individual_skills else "unknown",
            "nivel_habilidade": nivel_esperado,
            "registro_id": registro_id,
        }
        
        logger.info(f"Dados classificacao: {json.dumps(dados_classificacao, ensure_ascii=False)}")
        
        # Execute inference
        conteudo = await self._executar_inferencia(
            resposta_usuario=resposta_usuario,
            dados_classificacao=dados_classificacao
        )
        
        # Parse response to extract classification and justification
        classificacao, justificativa = self._parse_response(conteudo)
        
        logger.info(
            f"SkillEvaluator result: classificacao={classificacao}, "
            f"justificativa={justificativa[:100]}..."
        )
        
        # Return structured response (mimicking pydantic_ai output structure)
        class Output:
            def __init__(self, data: AgentSkillEvaluatorResponse):
                self.output = data
        
        return Output(AgentSkillEvaluatorResponse(
            classificacao=classificacao,
            justificativa=justificativa
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

        logger.info(f"SkillEvaluator system prompt: {system_message}")
        logger.info(f"SkillEvaluator user message: {resposta_usuario}")

        completion = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": resposta_usuario.strip()},
            ],
        )

        return completion.choices[0].message.content or ""

    def _parse_response(self, response: str) -> tuple[int, str]:
        """
        Parse model response to extract classification and justification.
        
        Expected format from fine-tuned model (new):
        {
            "adequacao_habilidades": "skill1:-1, skill2:0, skill3:1",
            "adequacao_macro": "-1"
        }
        
        Or legacy format:
        {
            "adequacao_habilidades": "1",
            "adequacao_habilidades_texto": "..."
        }
        
        Args:
            response: Raw model response
            
        Returns:
            Tuple of (classification, justification)
        """
        classificacao = 0  # default
        justificativa = response.strip()
        
        # Try to parse as JSON first
        try:
            data = json.loads(response)
            
            # NEW FORMAT: adequacao_macro is the main classification
            if "adequacao_macro" in data:
                classificacao = int(data["adequacao_macro"])
                
                # Build justification from adequacao_habilidades
                if "adequacao_habilidades" in data:
                    justificativa = f"Avaliação das habilidades: {data['adequacao_habilidades']}"
                else:
                    justificativa = "Classificação baseada na adequação macro"
                
                # Ensure classification is within bounds
                classificacao = max(-1, min(1, classificacao))
                return classificacao, justificativa
            
            # LEGACY FORMAT: adequacao_habilidades as classification
            if "adequacao_habilidades" in data:
                classificacao = int(data["adequacao_habilidades"])
                
                # Build justification from available fields
                justificativa_parts = []
                if "adequacao_habilidades_descricao" in data:
                    justificativa_parts.append(data["adequacao_habilidades_descricao"])
                if "adequacao_habilidades_texto" in data:
                    justificativa_parts.append(data["adequacao_habilidades_texto"])
                if "adequacao_habilidades_comentario" in data:
                    justificativa_parts.append(data["adequacao_habilidades_comentario"])
                
                justificativa = " ".join(justificativa_parts) if justificativa_parts else ""
                # Ensure classification is within bounds
                classificacao = max(-1, min(1, classificacao))
                return classificacao, justificativa
                
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        
        # Fallback: Try to extract from plain text format
        # Look for patterns like "Classificação: 0" or just a number at the start
        match = re.search(r'(?:classificação|classification)?\s*:?\s*(-?[01])', response, re.IGNORECASE)
        if match:
            classificacao = int(match.group(1))
            # Remove classification from justification
            justificativa = re.sub(
                r'(?:classificação|classification)\s*:?\s*-?[01]\s*', 
                '', 
                response, 
                count=1,
                flags=re.IGNORECASE
            ).strip()
        else:
            # Try to find just a number at the start
            match = re.match(r'^\s*(-?[01])\s*[:\-\.]?\s*(.*)', response, re.DOTALL)
            if match:
                classificacao = int(match.group(1))
                justificativa = match.group(2).strip()
        
        # Clean justification
        # Remove "Justificativa:" prefix if present
        justificativa = re.sub(
            r'^\s*(?:justificativa|justification)\s*:?\s*', 
            '',
            justificativa,
            flags=re.IGNORECASE
        ).strip()
        
        # Ensure classification is within bounds
        classificacao = max(-1, min(1, classificacao))
        
        return classificacao, justificativa
