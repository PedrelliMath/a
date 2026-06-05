from typing import Optional
from pydantic_ai import Agent
import os

from app.ai.agents.message_validator import (
    AgentMessageValidator,
    AgentMessageValidatorResponse,
)

from app.ai.agents.prompts import (
    message_validator,
    question_generator,
    skill_evaluator,
    supervisor,
)
from app.ai.agents.question_generator import (
    AgentQuestionGenerator,
    AgentQuestionGeneratorResponse,
)
from app.ai.agents.skill_evaluator import (
    AgentSkillEvaluator,
    AgentSkillEvaluatorResponse,
)
from app.ai.agents.supervisor import AgentSupervisor, AgentSupervisorResponse
from app.ai.agents.schemas.chat import ChatContextIn, ChatContextOut, ChatContextRunning
from app.ai.agents.helpers.transition_phrases import pick_transition_phrase
from app.models.session import Session
from app.logger import get_log
from app.observability import HeliconeContext
from app.config import settings

logger = get_log(__name__)


def get_proficiency_level(current_level: str, classification: int) -> str:
    """
    Calcula o próximo nível de proficiência baseado na classificação

    Args:
        current_level: Nível atual (lembrar, compreender, aplicar, analisar, avaliar, criar)
        classification: -1 (diminuir), 0 (manter), 1 (aumentar)

    Returns:
        Novo nível de proficiência
    """
    levels = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]

    current_level_normalized = current_level.lower()

    try:
        current_index = levels.index(current_level_normalized)
    except ValueError:
        logger.warning(f"Nível desconhecido: {current_level}, usando 'analisar'")
        return "analisar"

    new_index = max(0, min(current_index + classification, len(levels) - 1))

    return levels[new_index]


class AgentOrquestrator:
    """
    Orquestrador simples de agentes com fluxo linear:
    1. Validar mensagem do usuário
    2. Avaliar resposta (skill evaluation)
    3. Atualizar progresso
    4. Gerar nova pergunta

    Todos os outputs dos agentes são capturados em params para tracking.

    Nota: Este orquestrador NÃO salva mensagens. Ele apenas:
    - Lê o histórico de mensagens existente
    - Processa a nova mensagem do usuário
    - Retorna a resposta com params

    O salvamento das mensagens deve ser feito externamente após receber a resposta.
    """

    def __init__(self, session: Session, user_name: str | None = None):
        self.session = session
        self.context_in = None
        self.context_running = None
        # FIX #9: agents_params resetado por chamada em get_response, não só no __init__
        self.agents_params = {"prompt_version": "v2-neutral"}
        self.user_name = user_name or session.user_id

        self.agent_supervisor = None
        self.agent_message_validator = None
        self.agent_skill_evaluator = None
        self.agent_question_generator = None

    async def _init_agents(self):
        """Inicializa todos os agentes usando a configuração da skill"""

        if self.agent_supervisor is not None:
            logger.info("Agentes já inicializados")
            return

        logger.info(f"Inicializando agentes para skill: {self.session.skill.name}")

        skill = self.session.skill
        if not skill:
            raise ValueError("Session deve ter skill carregada")

        self.agents_config = skill.agents_config or {}
        logger.info(f"Configuração dos agentes carregada: {list(self.agents_config.keys())}")

        # FIX #7: create_model agora retorna model string apenas (temperature/max_tokens
        # devem ser passados via model_settings no Agent se necessário)
        def create_model(agent_name: str, default_model: str = "gpt-4o-mini") -> str:
            config = self.agents_config.get(agent_name, {})
            model_name = config.get("model_name", default_model)
            logger.info(f"Criando {agent_name}: model={model_name}")
            return f"openai:{model_name}"

        self.agent_supervisor = AgentSupervisor(
            runner=Agent(
                model=create_model("supervisor"),
                output_type=AgentSupervisorResponse,
            ),
            system_prompt=supervisor.system_prompt,
            retype_prompt=supervisor.retype_prompt,
            close_prompt=supervisor.close_prompt,
            message_prompt=supervisor.end_prompt,
            greeting_prompt=supervisor.greeting_prompt,
        )

        self.agent_message_validator = AgentMessageValidator(
            runner=Agent(
                model=create_model("message_validator"),
                output_type=AgentMessageValidatorResponse,
            ),
            system_prompt=message_validator.system_prompt,
            validation_prompt=message_validator.validation_prompt,
        )

        skill_eval_config = self.agents_config.get("skill_evaluator", {})
        model_id = skill_eval_config.get("model_name", "gpt-4o-mini")
        temperature = skill_eval_config.get("temperature", 0.0)
        justification_model_id = skill_eval_config.get("justification_model_name", "gpt-4o-mini")
        
        # Get base_url for helicone if enabled
        base_url = None
        if settings.helicone.is_configured:
            base_url = settings.helicone.helicone_base_url
            logger.info(f"Using Helicone base URL: {base_url}")

        self.agent_skill_evaluator = AgentSkillEvaluator(
            model_id=model_id,
            system_prompt_template=skill_evaluator.system_prompt_template,
            justification_prompt_template=skill_evaluator.justification_system_prompt_template,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            temperature=temperature,
            justification_model_id=justification_model_id,
        )

        logger.info(f"SkillEvaluator initialized with model: {model_id}")

        self.agent_question_generator = AgentQuestionGenerator(
            runner=Agent(
                model=create_model("question_generator"),
                output_type=AgentQuestionGeneratorResponse,
            ),
            generation_prompt=question_generator.user_prompt_generation,
            regeneration_prompt=question_generator.user_prompt_regeneration,
        )

    async def get_response(self, user_message: Optional[str]) -> ChatContextOut:
        """
        Processa a mensagem do usuário e retorna a resposta do chatbot.

        Args:
            user_message: Mensagem do usuário (None para saudação inicial)

        Returns:
            ChatContextOut com supervisor_message e params
        """
        # FIX #9: resetar agents_params a cada chamada para evitar contaminação entre requests
        self.agents_params = {}

        with HeliconeContext(
            session_id=str(self.session.id),
            user_id=self.session.user_id,
        ):
            try:
                await self._init_agents()

                self.context_in = await self._load_conversation_context(
                    is_greeting=user_message is None
                )

                self._init_running_context()

                if not user_message:
                    return await self._handle_greeting()

                return await self._process_user_message(user_message)

            except Exception as e:
                logger.error(f"Erro no AgentOrquestrador: {e}", exc_info=True)
                return self._error_response()

    def _init_running_context(self):
        """
        Inicializa o context_running com valores do context_in.
        Context running é mutável e será alterado durante o processamento.
        """
        self.context_running = ChatContextRunning(
            new_proficiency_level=self.context_in.current_proficiency_level,
            new_specific_skill=self.context_in.current_specific_skill,
        )
        self.current_question_set = self.context_in.current_question_set

        logger.info(
            f"Context running inicializado: "
            f"proficiency={self.context_running.new_proficiency_level}, "
            f"macrocompetencia={self.context_running.new_specific_skill}"
        )

    async def _load_conversation_context(self, is_greeting: bool = False) -> ChatContextIn:
        """Carrega todo o contexto necessário da session"""
        logger.info("Carregando contexto do chat")

        session_dict = self.session.to_dict(include_messages=True)
        message_history = session_dict.get("messages", [])
        skill = self.session.skill

        if not is_greeting and len(message_history) >= 2:
            ai_message = message_history[-2].get("text", "")
            user_response = message_history[-1].get("text", "")
        else:
            ai_message = ""
            user_response = ""

        skill_questions = skill.questions or {}
        rubrics = skill_questions.get("rubrics", {})
        bloom_levels = skill_questions.get("bloom_levels", {})

        if not skill_questions or not rubrics or not bloom_levels:
            raise Exception("O set de perguntas não está configurado corretamente.")

        current_proficiency_level, current_specific_skill = self._get_current_state(
            message_history, rubrics
        )

        current_question_set = self._get_question_set(
            current_proficiency_level,
            current_specific_skill,
            rubrics,
        )

        logger.info(
            f"Contexto carregado:\n"
            f"  Session ID: {self.session.id}\n"
            f"  Skill: {skill.name}\n"
            f"  Proficiency Level: {current_proficiency_level}\n"
            f"  Specific Skill: {current_specific_skill}\n"
            f"  Messages: {len(message_history)}\n"
            f"  Question Set: {len(current_question_set)} perguntas\n"
            f"  AI Message: {ai_message[:50]}...\n"
            f"  User Response: {user_response[:50]}..."
        )

        return ChatContextIn(
            session=self.session,
            ai_message=ai_message,
            user_response=user_response,
            current_proficiency_level=current_proficiency_level,
            current_question_set=current_question_set,
            current_specific_skill=current_specific_skill,
            message_history=message_history,
            rubrics=rubrics,
            bloom_levels=bloom_levels,
        )

    def _get_question_set(
        self,
        proficiency_level: str,
        specific_skill: str,
        rubrics: dict,
    ) -> list:
        level_normalized = proficiency_level.lower()
        skill_rubric = rubrics.get(specific_skill, {})
        questions = skill_rubric.get(level_normalized, [])

        logger.info(
            f"Question set: macrocompetencia={specific_skill}, "
            f"nivel de bloom={level_normalized}, quantidade de perguntas={len(questions)}"
        )

        return questions

    def _get_current_state(self, message_history: list, rubrics: dict) -> tuple[str, str]:
        available_skills = list(rubrics.keys())
        default_skill = available_skills[0] if available_skills else ""
        default_proficiency = "analisar"

        if len(message_history) < 2:
            logger.info(
                f"Primeira interação: usando macrocompetencia={default_skill}, "
                f"nivel de bloom={default_proficiency}"
            )
            return default_proficiency, default_skill

        last_bot_message = None
        for message in reversed(message_history):
            if message.get("user_type") == "bot":
                last_bot_message = message
                break

        if not last_bot_message:
            return default_proficiency, default_skill

        params = last_bot_message.get("params") or {}
        current_proficiency_level = params.get("new_proficiency_level", default_proficiency)
        current_specific_skill = params.get("new_specific_skill", default_skill)

        return current_proficiency_level, current_specific_skill

    def _count_messages_for_skill(self, messages: list, specific_skill: str) -> int:
        """Conta quantas mensagens do bot existem para uma skill específica."""
        count = 0

        for msg in messages:
            if msg.get("user_type") != "bot":
                continue

            params = msg.get("params") or {}
            tracker = params.get("progress_tracker") or {}
            validator = params.get("message_validator") or {}

            if tracker.get("should_continue") is False:
                continue

            is_supervisor_greeting = params.get("supervisor", {}).get("action") == "greeting"
            if is_supervisor_greeting:
                if params.get("new_specific_skill") == specific_skill:
                    count += 1
                continue

            flow = params.get("flow") or {}
            if flow.get("type") == "skip":
                if params.get("new_specific_skill") == specific_skill:
                    count += 1
                continue

            if not tracker:
                continue

            previous_skill = tracker.get("previous_skill")
            new_skill = tracker.get("new_skill")
            # FIX #4/#5: campo correto é "is_valid" após correção do validator
            is_valid = validator.get("is_valid") is True
            changed = tracker.get("changed_skill")

            if changed and is_valid:
                if new_skill == specific_skill:
                    count += 1
            elif not changed and is_valid:
                if previous_skill == specific_skill:
                    count += 1

        return count

    async def _handle_greeting(self) -> ChatContextOut:
        """Processa a saudação inicial"""
        logger.info("Processando saudação inicial")

        new_question = await self._generate_question()

        greeting_context = {
            "skill_name": self.context_in.session.skill.name,
            "subjects": list(self.context_in.rubrics.keys()),
            "user_name": self.user_name,
            "first_question": new_question,
        }

        result = await self.agent_supervisor.run_greeting(greeting_context)

        self.agents_params["supervisor"] = {"action": "greeting"}
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params,
        )

    async def _process_user_message(self, user_message: str) -> ChatContextOut:
        """Processa a mensagem do usuário através do fluxo completo"""
        logger.info("Processando a mensagem do usuário")

        # PASSO 1: Validar mensagem
        logger.info("PASSO 1: Validando mensagem do usuário")
        validation = await self._validate_message(user_message)

        # FIX #4: comparar com os valores corretos do schema ("invalid" / "incomplete")
        if validation.reason == "invalid":
            return await self._handle_invalid_message(validation)

        if validation.reason == "incomplete":
            return await self._handle_incomplete_message(validation)
        
        if validation.reason == "skip":
            return await self._handle_skip()

        # PASSO 2: Avaliar resposta
        logger.info("PASSO 2: Avaliando resposta do usuário")
        await self._evaluate_response(user_message)

        # PASSO 3: Atualizar progresso
        logger.info("PASSO 3: Atualizando progresso")
        should_continue = await self._update_progress()

        if not should_continue:
            logger.info("Encerrando conversa")
            return await self._handle_close()

        # PASSO 4: Gerar nova pergunta
        logger.info("PASSO 4: Gerando nova pergunta")
        new_question = await self._generate_question()

        # PASSO 5: Supervisor entrega a pergunta
        logger.info("PASSO 5: Gerando resposta do supervisor")
        supervisor_message = await self._generate_supervisor_response(new_question)

        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        pre_messages = self._build_transition_pre_messages()

        return ChatContextOut(
            supervisor_message=supervisor_message,
            params=self.agents_params,
            pre_messages=pre_messages,
        )
    
    async def _handle_skip(self) -> ChatContextOut:
        """Usuário desistiu da pergunta atual — avança sem avaliar."""
        logger.info("Usuário solicitou skip da pergunta atual")

        current_skill = self.context_running.new_specific_skill
        current_level = self.context_running.new_proficiency_level

        count_messages = self._count_messages_for_skill(
            self.context_in.message_history,
            current_skill,
        )

        if count_messages >= 2:
            specific_skill_list = list(self.context_in.rubrics.keys())
            try:
                idx = specific_skill_list.index(current_skill)
                next_idx = idx + 1

                if next_idx >= len(specific_skill_list):
                    self.agents_params["progress_tracker"] = {
                        "should_continue": False,
                        "reason": "No more skills available",
                    }
                    self.agents_params["flow"] = {"type": "skip"}
                    return await self._handle_close()

                new_skill = specific_skill_list[next_idx]
                self.context_running.new_specific_skill = new_skill
                self.context_running.new_proficiency_level = "analisar"
                self.current_question_set = self._get_question_set(
                    "analisar", new_skill, rubrics=self.context_in.rubrics
                )

                self.agents_params["progress_tracker"] = {
                    "should_continue": True,
                    "previous_skill": current_skill,
                    "new_skill": new_skill,
                    "changed_skill": True,
                    "reset_proficiency": True,
                }

            except ValueError:
                logger.error(f"Skill não encontrada: {current_skill}")
                return self._error_response()
        else:
            levels = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]
            current_idx = levels.index(current_level.lower()) if current_level.lower() in levels else -1

            alt_question_set = []
            for delta in [1, -1]:
                alt_idx = current_idx + delta
                if 0 <= alt_idx < len(levels):
                    candidate = self._get_question_set(
                        levels[alt_idx], current_skill, rubrics=self.context_in.rubrics
                    )
                    if candidate:
                        alt_question_set = candidate
                        logger.info(
                            f"Skip: usando perguntas do nível {levels[alt_idx]} "
                            f"para evitar repetição (proficiency mantido: {current_level})"
                        )
                        break

            self.current_question_set = alt_question_set or self._get_question_set(
                current_level, current_skill, rubrics=self.context_in.rubrics
            )

            self.agents_params["progress_tracker"] = {
                "should_continue": True,
                "previous_skill": current_skill,
                "new_skill": current_skill,
                "changed_skill": False,
            }

        new_question = await self._generate_question()
        supervisor_message = await self._generate_supervisor_response(new_question)

        self.agents_params["flow"] = {"type": "skip"}
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=supervisor_message,
            params=self.agents_params,
        )
                
    def _build_transition_pre_messages(self) -> list[dict] | None:
        tracker = self.agents_params.get("progress_tracker") or {}
        if not tracker.get("changed_skill"):
            return None

        used = [
            (msg.get("params") or {}).get("transition_phrase")
            for msg in self.context_in.message_history
            if msg.get("user_type") == "bot"
            and (msg.get("params") or {}).get("transition_phrase")
        ]
        phrase = pick_transition_phrase(used)

        logger.info(
            f"Transicao de topico: {tracker.get('previous_skill')} -> "
            f"{tracker.get('new_skill')} | frase sorteada: {phrase}"
        )

        return [
            {
                "text": phrase,
                "params": {
                    "transition_phrase": phrase,
                    "previous_skill": tracker.get("previous_skill"),
                    "new_skill": tracker.get("new_skill"),
                },
            }
        ]

    async def _generate_supervisor_response(
        self, new_question: str, flow_type: str = "normal"
    ) -> str:
        """Gera a resposta do supervisor para retornar ao usuário"""
        if flow_type == "followup":
            flow_context = (
                "### Contexto do Fluxo\n"
                "A resposta anterior do usuário estava INCOMPLETA.\n"
                "NÃO resuma nem repita o que o usuário disse.\n"
                "Vá direto ao ponto: sinalize brevemente (em meia frase) que a resposta "
                "precisava de mais profundidade, e então faça a nova pergunta.\n"
            )
        else:
            levels = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]
            current_idx = levels.index(current_level.lower()) if current_level.lower() in levels else -1

            alt_question_set = []
            for delta in [1, -1]:
                alt_idx = current_idx + delta
                if 0 <= alt_idx < len(levels):
                    candidate = self._get_question_set(
                        levels[alt_idx], current_skill, rubrics=self.context_in.rubrics
                    )
                    if candidate:
                        alt_question_set = candidate
                        logger.info(
                            f"Skip: usando perguntas do nível {levels[alt_idx]} "
                            f"para evitar repetição (proficiency mantido: {current_level})"
                        )
                        break

            self.current_question_set = alt_question_set or self._get_question_set(
                current_level, current_skill, rubrics=self.context_in.rubrics
            )

            self.agents_params["progress_tracker"] = {
                "should_continue": True,
                "previous_skill": current_skill,
                "new_skill": current_skill,
                "changed_skill": False,
            }

        new_question = await self._generate_question()
        supervisor_message = await self._generate_supervisor_response(new_question)

        self.agents_params["flow"] = {"type": "skip"}
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=supervisor_message,
            params=self.agents_params,
        )

    async def _generate_supervisor_response(self, new_question: str) -> str:
        end_context = {
            "message_history": self.context_in.get_message_history(4),
            "current_subject": self.context_in.current_specific_skill,
            "generated_question": new_question,
            "flow_context": "",
        }

        result = await self.agent_supervisor.run_end(end_context)
        self.agents_params["supervisor"] = {"action": "end"}
        return result.output.message

    def _get_invalid_history(self) -> str:
        """
        Retorna histórico formatado das respostas inválidas do usuário
        para a skill atual, para dar contexto ao message validator.
        """
        current_skill = self.context_running.new_specific_skill
        invalid_entries = []

        for msg in self.context_in.message_history:
            if msg.get("user_type") == "bot":
                continue

            # Pegar a mensagem bot anterior (pergunta feita ao usuário)
            idx = self.context_in.message_history.index(msg)
            if idx == 0:
                continue

            prev_bot = None
            for m in reversed(self.context_in.message_history[:idx]):
                if m.get("user_type") == "bot":
                    prev_bot = m
                    break

            if not prev_bot:
                continue

            params = prev_bot.get("params") or {}
            validator = params.get("message_validator") or {}
            skill = params.get("new_specific_skill")

            # Filtrar apenas inválidas da skill atual
            if skill != current_skill:
                continue
            if validator.get("is_valid") is not False:
                continue

            pergunta = prev_bot.get("text", "")
            resposta = msg.get("text", "")
            motivo = validator.get("explicacao", "")

            invalid_entries.append(
                f"- Pergunta: {pergunta}\n"
                f"  Resposta inválida: {resposta}\n"
                f"  Motivo: {motivo}"
            )

        if not invalid_entries:
            return "Nenhuma tentativa inválida anterior."

        return "\n".join(invalid_entries)

    async def _validate_message(self, user_message: str):
        """Valida se a mensagem do usuário está adequada"""
        logger.info("Validando mensagem do usuário")
        result = await self.agent_message_validator.run_validation(
            {
                "message_history":self.context_in.get_message_history(),
                "user_message": user_message,
                "question": self.context_in.ai_message,
                "invalid_history": self._get_invalid_history(),
            }
        )

        output = result.output

        # FIX #4: usar os campos corretos do AgentMessageValidatorResponse
        self.agents_params["message_validator"] = {
            "is_valid": output.is_valid,
            "reason": output.reason,
            "explicacao": output.explicacao,
            "missing_parts": output.missing_parts,
            "followup_instruction": (
                output.followup_instruction.model_dump()
                if output.followup_instruction
                else None
            ),
        }

        return output

    async def _evaluate_response(self, user_message: str):
        """Avalia a resposta do usuário e atualiza o proficiency level no context_running"""
        logger.info("Avaliando mensagem do usuário")

        evaluation_context = {
            "user_message": user_message,
            "question": self.context_in.ai_message,
            "current_proficiency_level": self.context_running.new_proficiency_level,
            "current_specific_skill": self.context_running.new_specific_skill,
            "current_question_set": self.current_question_set,
            "rubrics": self.context_in.rubrics,
            "bloom_levels": self.context_in.bloom_levels,
            "session": self.session,
        }

        result = await self.agent_skill_evaluator.run_evaluation(evaluation_context)

        classificacao = result.output.classificacao
        adequacao_habilidades = result.output.adequacao_habilidades
        adequacao_macro = result.output.adequacao_macro
        justificativas_habilidades = result.output.justificativas_habilidades
        current_level = self.context_running.new_proficiency_level

        new_level = (
            get_proficiency_level(current_level, classificacao)
            if classificacao != 0
            else current_level
        )

        self.context_running.new_proficiency_level = new_level

        self.agents_params["skill_evaluator"] = {
            "classification": classificacao,
            "adequacao_habilidades": adequacao_habilidades,
            "justificativas_habilidades": justificativas_habilidades,
            "adequacao_macro": adequacao_macro,
            "expected_level": current_level,
            "achieved_level": new_level,
        }

        logger.info(
            f"Avaliação: {classificacao} (macro: {adequacao_macro})\n"
            f"Habilidades: {adequacao_habilidades}\n"
            f"Justificativas: {justificativas_habilidades}\n"
            f"Nível: {current_level} -> {new_level}"
        )

    async def _update_progress(self) -> bool:
        """
        Atualiza o progresso e verifica se deve mudar de skill.

        Returns:
            bool: should_continue
        """
        logger.info("Atualizando progresso do chat")

        current_level = self.context_running.new_proficiency_level
        current_skill = self.context_running.new_specific_skill

        # Verifica se o nível mudou (classificacao != 0)
        skill_evaluator_params = self.agents_params.get("skill_evaluator", {})
        classification = skill_evaluator_params.get("classification", 0)

        # Carrega o question set do nível atual
        self.current_question_set = self._get_question_set(
            proficiency_level=current_level,
            specific_skill=current_skill,
            rubrics=self.context_in.rubrics,
        )

        # Se classificacao == 0 (nível mantido), usa perguntas do nível acima
        # para evitar repetição sem alterar o proficiency persistido
        if classification == 0:
            levels = ["lembrar", "compreender", "aplicar", "analisar", "avaliar", "criar"]
            current_idx = levels.index(current_level.lower()) if current_level.lower() in levels else -1
            next_idx = min(current_idx + 1, len(levels) - 1)

            if next_idx != current_idx:
                next_level = levels[next_idx]
                upper_question_set = self._get_question_set(
                    proficiency_level=next_level,
                    specific_skill=current_skill,
                    rubrics=self.context_in.rubrics,
                )
                if upper_question_set:
                    logger.info(
                        f"Classificacao 0: usando perguntas do nível acima "
                        f"({current_level} -> {next_level}) sem alterar proficiency persistido"
                    )
                    self.current_question_set = upper_question_set
            else:
                logger.info(
                    f"Classificacao 0: já no nível máximo ({current_level}), "
                    f"mantendo question set atual"
                )

        count_messages = self._count_messages_for_skill(
            self.context_in.message_history,
            current_skill,
        )

        logger.info(
            f"Macrocompetencia: {current_skill}\n"
            f"Perguntas já realizadas: {count_messages}"
        )

        should_change_skill = count_messages >= 2

        if should_change_skill:
            specific_skill_list = list(self.context_in.rubrics.keys())

            try:
                specific_skill_idx = specific_skill_list.index(current_skill)
                next_idx = specific_skill_idx + 1

                if next_idx >= len(specific_skill_list):
                    self.agents_params["progress_tracker"] = {
                        "should_continue": False,
                        "reason": "No more skills available",
                    }
                    return False

                new_specific_skill = specific_skill_list[next_idx]

                self.context_running.new_specific_skill = new_specific_skill
                self.context_running.new_proficiency_level = "analisar"

                self.current_question_set = self._get_question_set(
                    "analisar",
                    new_specific_skill,
                    rubrics=self.context_in.rubrics,
                )

                logger.info(
                    f"Mudando skill: {current_skill} -> "
                    f"{new_specific_skill}, reset proficiency para 'analisar'"
                )

                self.agents_params["progress_tracker"] = {
                    "should_continue": True,
                    "previous_skill": current_skill,
                    "new_skill": new_specific_skill,
                    "changed_skill": True,
                    "reset_proficiency": True,
                }

            except ValueError:
                logger.error(f"Skill não encontrada: {current_skill}")
                return False
        else:
            self.agents_params["progress_tracker"] = {
                "should_continue": True,
                "previous_skill": current_skill,
                "new_skill": current_skill,
                "changed_skill": False,
            }

        return True

    async def _generate_question(self) -> str:
        """Gera uma nova pergunta para o usuário usando context_running"""
        logger.info("Gerando nova pergunta para o usuário")

        generation_context = {
            "message_history": self.context_in.get_message_history(),
            "current_specific_skill": self.context_running.new_specific_skill,
            "current_proficiency_level": self.context_running.new_proficiency_level,
            "current_question_set": self.current_question_set,
            "user_id": self.context_in.session.user_id,
            "skill": self.context_in.session.skill,
        }

        result = await self.agent_question_generator.run_generation(generation_context)

        question = result.output.pergunta

        self.agents_params["question_generator"] = {
            "question": question,
            "action": "generate",
        }

        logger.info(f"Nova pergunta gerada: {question[:100]}...")

        return question

    async def _regenerate_question(self) -> str:
        """
        Regenera a pergunta atual (quando usuário enviou resposta inválida).
        """
        logger.info("Regenerando pergunta")

        validator = self.agents_params["message_validator"]

        # Campos alinhados com user_prompt_regeneration:
        # {past_question}, {past_answer}, {intent}, {focus}, {constraints}
        regeneration_context = {
            "past_question": self.context_in.message_history[-2]["text"],
            "past_answer": self.context_in.message_history[-1]["text"],
            "intent": "reformular",
            "focus": validator["explicacao"] or "resposta inválida ou fora do contexto",
            "constraints": ", ".join(validator.get("missing_parts") or []) or "nenhuma restrição adicional",
        }

        result = await self.agent_question_generator.run_regeneration(regeneration_context)

        question = result.output.pergunta

        self.agents_params["question_generator"] = {
            "question": question,
            "action": "regenerate",
        }

        logger.info(f"Pergunta regenerada: {question[:100]}...")

        return question

    async def _handle_invalid_message(self, validation) -> ChatContextOut:
        """
        Trata mensagens inválidas:
        1. Regenera a pergunta
        2. Supervisor adiciona feedback de validação
        """
        logger.info("Tratando mensagem inválida")

        regenerated_question = await self._regenerate_question()

        # FIX #3: passar regenerated_question ao supervisor
        retype_context = {
            "message_history": self.context_in.get_message_history(),
            "validation_feedback": validation,
            "regenerated_question": regenerated_question,
        }

        result = await self.agent_supervisor.run_retype(retype_context)

        self.agents_params["supervisor"] = {"action": "retype"}
        self.agents_params["flow"] = {
            "type": "retry",
            "reason": "invalid_answer",
        }
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params,
        )

    async def _handle_incomplete_message(self, validation) -> ChatContextOut:
        """Trata mensagens incompletas gerando uma pergunta de follow-up"""
        logger.info("Resposta incompleta detectada")

        instruction = validation.followup_instruction

        # FIX #8: campos alinhados com user_prompt_regeneration
        # {past_question}, {past_answer}, {intent}, {focus}, {constraints}
        regeneration_context = {
            "past_question": self.context_in.ai_message,
            "past_answer": self.context_in.user_response,
            "intent": instruction.intent,
            "focus": instruction.focus,
            "constraints": ", ".join(instruction.constraints) if instruction.constraints else "nenhuma restrição adicional",
        }

        result = await self.agent_question_generator.run_regeneration(regeneration_context)

        question = result.output.pergunta

        self.agents_params["question_generator"] = {
            "question": question,
            "action": "followup",
            "based_on": "incomplete_answer",
        }
        self.agents_params["flow"] = {
            "type": "followup",
            "reason": "incomplete_answer",
        }

        supervisor_message = await self._generate_supervisor_response(question)

        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=supervisor_message,
            params=self.agents_params,
        )

    async def _handle_close(self) -> ChatContextOut:
        """Encerra a conversa"""
        logger.info("Encerrando o chat")

        supervisor_context = {
            "message_history": self.context_in.get_message_history(),
        }

        result = await self.agent_supervisor.run_close(supervisor_context)

        self.agents_params["supervisor"] = {"action": "close"}
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params,
        )

    def _error_response(self) -> ChatContextOut:
        """Resposta padrão para erros"""
        logger.error("Gerando resposta de erro")
        return ChatContextOut(
            supervisor_message="Desculpe, ocorreu um erro interno. Tente novamente.",
            params={},
        )


def create_agent_orquestrator(session: Session, user_name: str | None = None) -> AgentOrquestrator:
    """
    Factory function para criar AgentOrquestrator
    Args:
        session: Objeto Session do banco (já carregado com skill)
        user_name: Nome do usuário (do JWT). Se None, usa user_id.
    Returns:
        AgentOrquestrator configurado
    Exemplo:
        # Buscar session do banco
        session = await session_repo.get_by_id(session_id)
        # Criar orquestrador
        orchestrator = create_agent_orquestrator(session, user_name="João")
        # Usar
        response = await orchestrator.get_response(user_message)
    """
    return AgentOrquestrator(session, user_name=user_name)