from typing import Optional
from uuid import UUID
from pydantic_ai import Agent

from app.ai.agents.message_validator import (
    AgentMessageValidator,
    AgentMessageValidatorResponse,
)

from app.ai.agents.prompts import (
    message_validator,
    progress_tracker,
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
from app.models.session import Session
from app.logger import get_log
from app.observability import HeliconeContext

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
    
    # Normalizar para lowercase
    current_level_normalized = current_level.lower()
    
    try:
        current_index = levels.index(current_level_normalized)
    except ValueError:
        # Se não encontrar, retorna analisar
        logger.warning(f"Nível desconhecido: {current_level}, usando 'analisar'")
        return "analisar"
    
    # Calcular novo índice
    new_index = current_index + classification
    
    # Garantir que está dentro dos limites
    new_index = max(0, min(new_index, len(levels) - 1))
    
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

    def __init__(self, session: Session):
        """
        Inicializa o orquestrador com uma session.
        
        Args:
            session: Objeto Session do banco (já carregado com skill)
        """
        self.session = session
        self.context_in = None
        self.context_running = None
        self.agents_params = {}

        # Agentes serão inicializados na primeira chamada
        self.agent_supervisor = None
        self.agent_message_validator = None
        self.agent_skill_evaluator = None
        self.agent_progress_tracker = None
        self.agent_question_generator = None

    async def _init_agents(self):
        """Inicializa todos os agentes usando a configuração da skill"""
        
        # Se já foi inicializado, não precisa reinicializar
        if self.agent_supervisor is not None:
            logger.info("Agentes já inicializados")
            return
        
        logger.info(f"Inicializando agentes para skill: {self.session.skill.name}")
        
        skill = self.session.skill
        if not skill:
            raise ValueError("Session deve ter skill carregada")
        
        # Pegar configuração dos agentes
        self.agents_config = skill.agents_config or {}
        logger.info(f"Configuração dos agentes carregada: {list(self.agents_config.keys())}")

        # Helper para criar modelo com config
        def create_model(agent_name: str, default_model: str = "gpt-4o-mini"):
            config = self.agents_config.get(agent_name, {})
            model_name = config.get("model_name", default_model)
            temperature = config.get("temperature", 0.3)
            max_tokens = config.get("max_tokens", 1000)
            
            logger.info(
                f"Criando {agent_name}: model={model_name}, "
                f"temp={temperature}, max_tokens={max_tokens}"
            )
            
            return f"openai:{model_name}"

        # Inicializar cada agente com sua config específica
        self.agent_supervisor = AgentSupervisor(
            runner=Agent(
                model=create_model("supervisor"),
                output_type=AgentSupervisorResponse
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
                output_type=AgentMessageValidatorResponse
            ),
            system_prompt=message_validator.system_prompt,
            validation_prompt=message_validator.validation_prompt,
        )

        self.agent_skill_evaluator = AgentSkillEvaluator(
            runner=Agent(
                model=create_model("skill_evaluator"),
                output_type=AgentSkillEvaluatorResponse
            ),
            system_prompt=skill_evaluator.system_prompt,
            evaluation_prompt=skill_evaluator.evaluation_prompt,
        )

        self.agent_question_generator = AgentQuestionGenerator(
            runner=Agent(
                model=create_model("question_generator"),
                output_type=AgentQuestionGeneratorResponse
            ),
            generation_prompt=question_generator.user_prompt_generation,
            regeneration_prompt=question_generator.user_prompt_regeneration,
        )

    async def get_response(self, user_message: Optional[str]) -> ChatContextOut:
        """
        Processa a mensagem do usuário e retorna a resposta do chatbot.
        
        Args:
            user_message: Mensagem do usuário (None para saudação inicial)
        
        Fluxo:
        1. Se é primeira mensagem -> Saudação
        2. Validar mensagem
           - Se inválida -> Regenerar pergunta + feedback
           - Se válida -> Continuar
        3. Avaliar resposta (atualizar proficiency)
        4. Atualizar progresso (mudar skill se necessário)
        5. Gerar nova pergunta
        
        Returns:
            ChatContextOut com:
            - supervisor_message: mensagem final para o usuário
            - new_proficiency_level: nível de proficiência atualizado
            - new_specific_skill: skill específica atualizada
            - params: dict com outputs de todos os agentes executados
        
        Nota: As mensagens NÃO são salvas aqui. Isso deve ser feito após
        receber a resposta deste método.
        """
        # Configurar contexto do Helicone para observabilidade
        with HeliconeContext(
            session_id=str(self.session.id),
            user_id=self.session.user_id
        ):
            try:
                # Inicializar agentes se ainda não foram (primeira chamada)
                await self._init_agents()
                
                # Carregar contexto da conversa (context_in é imutável)
                self.context_in = await self._load_conversation_context(
                    is_greeting=user_message is None
                )
                
                # Inicializar context_running com valores do context_in
                self._init_running_context()

                # Caso especial: primeira interação
                if not user_message:
                    return await self._handle_greeting()

                # Fluxo normal: processar mensagem do usuário
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
        # Guardar question_set separadamente já que não está no schema
        self.current_question_set = self.context_in.current_question_set
        
        logger.info(
            f"Context running inicializado: "
            f"proficiency={self.context_running.new_proficiency_level}, "
            f"macrocompetencia={self.context_running.new_specific_skill}"
        )

    async def _load_conversation_context(self, is_greeting: bool = False) -> ChatContextIn:
        """Carrega todo o contexto necessário da session"""
        logger.info("Carregando contexto do chat")
        # Converter para dict e pegar messages
        session_dict = self.session.to_dict(include_messages=True)
        message_history = session_dict.get('messages', [])
        skill = self.session.skill
        user_id = self.session.user_id

        # No greeting, não há pergunta/resposta anterior
        if not is_greeting and len(message_history) >= 2:
            ai_message = message_history[-2].get('text', '')
            user_response = message_history[-1].get('text', '')
        else:
            ai_message = ""
            user_response = ""

        # Pegar questions da skill
        skill_questions = skill.questions or {}
        rubrics = skill_questions.get('rubrics', {})
        bloom_levels = skill_questions.get('bloom_levels', {})

        if not skill_questions or not rubrics or not bloom_levels:
            raise Exception("O set de perguntas não está configurado corretamente.")

        # Determinar estado atual baseado no histórico
        current_proficiency_level, current_specific_skill = (
            self._get_current_state(message_history, rubrics)
        )

        # Pegar o question set atual baseado na skill
        current_question_set = self._get_question_set(
            current_proficiency_level, 
            current_specific_skill,
            rubrics
        )

        logger.info(
            f"Contexto carregado:\n"
            f"  Session ID: {self.session.id}\n"
            f"  Skill: {skill.name}\n"
            f"  Proficiency Level: {current_proficiency_level}\n"
            f"  Specific Skill: {current_specific_skill}\n"
            f"  Question: {current_question}\n"
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
        rubrics: dict
    ) -> list:
        """
        Busca o set de perguntas para o nível e skill específicos
        
        Args:
            proficiency_level: Nível Bloom (lembrar, compreender, aplicar, analisar, avaliar, criar)
            specific_skill: Nome da skill/competência
            rubrics: Dict de rubrics da skill
            
        Returns:
            Lista de perguntas ou lista vazia se não encontrado
        """
        # Normalizar proficiency_level para lowercase
        level_normalized = proficiency_level.lower()
        
        # Buscar no rubrics
        skill_rubric = rubrics.get(specific_skill, {})
        questions = skill_rubric.get(level_normalized, [])
        
        logger.info(
            f"Question set: macrocompetencia={specific_skill}, "
            f"nivel de bloom={level_normalized}, quantidade de perguntas={len(questions)}"
        )
        
        return questions

    def _get_current_state(self, message_history: list, rubrics: dict) -> tuple[str, str]:
        """
        Extrai o estado atual (nivel de proficiência e macrocompetência) do histórico
        
        Args:
            message_history: Lista de mensagens
            rubrics: Dict de rubricas da skill
            
        Returns:
            (proficiency_level, specific_skill)
        """
        # Pegar a primeira skill disponível nas rubrics
        available_skills = list(rubrics.keys())
        default_skill = available_skills[0] if available_skills else ""
        
        # Sempre começa em "analisar"
        default_proficiency = "analisar"

        if len(message_history) < 2:
            logger.info(
                f"Primeira interação: usando macrocompetencia={default_skill}, "
                f"nivel de bloom={default_proficiency}"
            )
            return default_proficiency, default_skill

        # Busca a última mensagem do bot
        last_bot_message = None
        for message in reversed(message_history):
            if message.get("user_type") == "bot":
                last_bot_message = message
                break
        
        if not last_bot_message:
            return default_proficiency, default_skill
        
        # Pega parâmetros da última mensagem do bot
        params = last_bot_message.get("params") or {}
        current_proficiency_level = params.get("new_proficiency_level", default_proficiency)
        current_specific_skill = params.get("new_specific_skill", default_skill)

        return current_proficiency_level, current_specific_skill

    def _count_messages_for_skill(self, messages: list, specific_skill: str) -> int:
        """Conta quantas mensagens do bot existem para uma skill específica,
        incluindo a pergunta inicial do supervisor.
        """
        count = 0
    
        for msg in messages:
            if msg.get("user_type") != "bot":
                continue
            
            params = msg.get("params") or {}
            tracker = params.get("progress_tracker") or {}
            validator = params.get("message_validator") or {}
            
            # Ignora mensagem de encerramento
            if tracker.get("should_continue") is False:
                continue
            
            # Caso 1: Mensagem de greeting (primeira pergunta da skill)
            # Conta baseado no new_specific_skill e is_valid
            is_supervisor_greeting = params.get("supervisor", {}).get("action") == "greeting"
            if is_supervisor_greeting:
                new_specific_skill = params.get("new_specific_skill")
                if new_specific_skill == specific_skill:
                    count += 1
                continue
            
            # Caso 2: Mensagens normais (não greeting)
            # A resposta do usuário é sempre para previous_skill
            if not tracker:
                continue
                
            previous_skill = tracker.get("previous_skill")
            new_skill = tracker.get("new_skill")
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

        # Gerar primeira pergunta usando context_running
        new_question = await self._generate_question()

        greeting_context = {
            "skill_name": self.context_in.session.skill.name,
            "subjects": list(self.context_in.rubrics.keys()),
            "user_name": self.context_in.session.user_id,
            "first_question": new_question
        }

        result = await self.agent_supervisor.run_greeting(greeting_context)
        
        # Capturar output do supervisor
        self.agents_params["supervisor"] = {
            "action": "greeting"
        }
        
        # Adicionar proficiency e skill aos params
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params
        )

    async def _process_user_message(self, user_message: str) -> ChatContextOut:
        """Processa a mensagem do usuário através do fluxo completo"""
        logger.info("Processando a mensagem do usuário")
        
        # PASSO 1: Validar mensagem
        logger.info("PASSO 1: Validando mensagem do usuário")
        is_valid, validation_feedback = await self._validate_message(user_message)

        if not is_valid:
            logger.info(f"Mensagem inválida: {validation_feedback}")
            return await self._handle_invalid_message(validation_feedback)

        # PASSO 2: Avaliar resposta (skill evaluation)
        logger.info("PASSO 2: Avaliando resposta do usuário")
        await self._evaluate_response(user_message)

        # PASSO 3: Atualizar progresso (verificar se deve mudar de macrocompetencia)
        logger.info("PASSO 3: Atualizando progresso")
        should_continue = await self._update_progress()

        # Se não deve continuar, encerrar conversa
        if not should_continue:
            logger.info("Encerrando conversa")
            return await self._handle_close()

        # PASSO 4: Gerar nova pergunta
        logger.info("PASSO 4: Gerando nova pergunta")
        new_question = await self._generate_question()

        # PASSO 5: Entrega a pergunta para o supervisor
        logger.info("PASSO 5: Gerando resposta  do supervisor")
        supervisor_message = await self._generate_supervisor_response(new_question)
        
        # Adicionar proficiency e skill aos params
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=supervisor_message,
            params=self.agents_params
        )
    
    async def _generate_supervisor_response(self, new_question: str):
        """Gera a resposta do supervisor para retornar ao usuario"""
        end_context = {
            "message_history":self.context_in.get_message_history(4),
            "current_subject":self.context_in.current_specific_skill,
            "generated_question":new_question
        }

        result = await self.agent_supervisor.run_end(end_context)

        self.agents_params["supervisor"] = {
            "action":"end"
        }

        return result.output.message

    async def _validate_message(self, user_message: str) -> tuple[bool, str]:
        """Valida se a mensagem do usuário está adequada"""
        logger.info("Validando mensagem do usuário")
        # Preparar contexto para validação
        validation_context = {
            "message_history":self.context_in.get_message_history(),
            "user_message": user_message,
            "question": self.context_in.ai_message,
        }

        result = await self.agent_message_validator.run_validation(
            validation_context
        )

        is_valid = result.output.is_valid
        feedback = result.output.explicacao or ""
        
        # Capturar output do validator
        self.agents_params["message_validator"] = {
            "is_valid": is_valid,
            "feedback": feedback,
        }

        logger.info(f"Validação: {is_valid} - {feedback}")
        return is_valid, feedback

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
        }
        
        result = await self.agent_skill_evaluator.run_evaluation(evaluation_context)

        classificacao = result.output.classificacao
        justificativa = result.output.justificativa
        current_level = self.context_running.new_proficiency_level

        # Calcular novo nível baseado na classificação
        if classificacao != 0:
            new_level = get_proficiency_level(current_level, classificacao)

        else:
            new_level = current_level
        
        # ATUALIZAR CONTEXT RUNNING
        self.context_running.new_proficiency_level = new_level
        
        # Capturar output do evaluator
        self.agents_params["skill_evaluator"] = {
            "classification": classificacao,
            "justification": justificativa,
            "expected_level": current_level,
            "achieved_level": new_level,
        }

        logger.info(
            f"Avaliação: {classificacao} ({justificativa})\n"
            f"Nível: {current_level} -> {new_level}"
        )

    async def _update_progress(self) -> bool:
        """
        Atualiza o progresso e verifica se deve mudar de skill.
        Atualiza context_running com nova skill se necessário.
        
        Returns:
            bool: should_continue
        """
        logger.info("Atualizando progresso do chat")

        self.current_question_set = self._get_question_set(
            proficiency_level=self.context_running.new_proficiency_level,
            specific_skill=self.context_running.new_specific_skill,
            rubrics=self.context_in.rubrics
        )

        # Contar mensagens para a skill atual
        count_messages = self._count_messages_for_skill(
            self.context_in.message_history, 
            self.context_running.new_specific_skill
        )

        logger.info(
            f"Macrocompetencia: {self.context_running.new_specific_skill}\n"
            f"Perguntas já realizadas: {count_messages}"
        )

        # Se já tem 2+ mensagens, mudar para próxima skill
        should_change_skill = count_messages >= 2
        
        if should_change_skill:
            # Lista todas as macrocompetencias
            specific_skill_list = list(self.context_in.rubrics.keys())
            
            # Encontra na lista a macrocompetencia atual
            try:
                specific_skill_idx = specific_skill_list.index(
                    self.context_running.new_specific_skill
                )
                next_idx = specific_skill_idx + 1
                
                # Verifica se há próxima skill
                if next_idx >= len(specific_skill_list):
                    # Não há mais skills, encerrar
                    self.agents_params["progress_tracker"] = {
                        "should_continue": False,
                        "reason": "No more skills available"
                    }
                    return False
                
                # Pegar próxima skill
                new_specific_skill = specific_skill_list[next_idx]
                
                # Reset proficiency para "analisar" ao mudar de skill
                self.context_running.new_specific_skill = new_specific_skill
                self.context_running.new_proficiency_level = "analisar"
                
                # Atualizar question set
                self.current_question_set = self._get_question_set(
                    "analisar",
                    new_specific_skill,
                    rubrics=self.context_in.rubrics
                )
                
                logger.info(
                    f"Mudando skill: {self.context_in.current_specific_skill} -> "
                    f"{new_specific_skill}, reset proficiency para 'analisar'"
                )
                
                # Capturar output do tracker
                self.agents_params["progress_tracker"] = {
                    "should_continue": True,
                    "previous_skill": self.context_in.current_specific_skill,
                    "new_skill": new_specific_skill,
                    "changed_skill": True,
                    "reset_proficiency": True
                }
                
            except ValueError:
                # Skill atual não encontrada, erro
                logger.error(f"Skill não encontrada: {self.context_running.new_specific_skill}")
                return False
        else:
            # Não muda skill, apenas continua
            self.agents_params["progress_tracker"] = {
                "should_continue": True,
                "previous_skill": self.context_running.new_specific_skill,
                "new_skill": self.context_running.new_specific_skill,
                "changed_skill": False,
            }

        return True

    async def _generate_question(self) -> str:
        """Gera uma nova pergunta para o usuário usando context_running"""
        logger.info("Gerando nova pergunta para o usuario")
        
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
        
        # Capturar output do generator
        self.agents_params["question_generator"] = {
            "question": question,
            "action": "generate",
        }
        
        logger.info(f"Nova pergunta gerada: {question[:100]}...")
        
        return question

    async def _regenerate_question(self) -> str:
        """
        Regenera a pergunta atual (quando usuário enviou resposta inválida).
        Usa o question regenerator ao invés do generator.
        """
        logger.info("Regenerando pergunta")
        
        regeneration_context = {
            "bot_message":self.context_in.message_history[-2]['text'],
            "user_response":self.context_in.message_history[-1]['text'],
            "message_history": self.context_in.message_history,
            "current_specific_skill": self.context_running.new_specific_skill,
            "current_proficiency_level": self.context_running.new_proficiency_level,
            "current_question_set": self.current_question_set,
            "validator_feedback":self.agents_params["message_validator"]["feedback"],
            "message_history":self.context_in.get_message_history(2),
            "user_id": self.context_in.session.user_id,
            "skill": self.context_in.session.skill,
        }

        result = await self.agent_question_generator.run_regeneration(regeneration_context)

        question = result.output.pergunta
        
        # Capturar output do regenerator
        self.agents_params["question_generator"] = {
            "question": question,
            "action": "regenerate",
        }
        
        logger.info(f"Pergunta regenerada: {question[:100]}...")
        
        return question

    async def _handle_invalid_message(self, validation_feedback: str) -> ChatContextOut:
        """
        Trata mensagens inválidas:
        1. Regenera a pergunta (question regenerator)
        2. Supervisor adiciona feedback de validação
        """
        logger.info("Tratando mensagem inválida")
        
        # PASSO 1: Regenerar a pergunta
        logger.info("Regenerando pergunta devido a mensagem inválida")
        regenerated_question = await self._regenerate_question()
        
        # PASSO 2: Supervisor adiciona feedback explicando o problema
        retype_context = {
            "message_history": self.context_in.get_message_history(),
            "validation_feedback": validation_feedback,
        }

        result = await self.agent_supervisor.run_retype(retype_context)
        
        # Capturar output do supervisor
        self.agents_params["supervisor"] = {
            "action": "retype",
        }
        
        # Adicionar proficiency e skill aos params
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params
        )

    async def _handle_close(self) -> ChatContextOut:
        """Encerra a conversa"""
        logger.info("Encerrando o chat")

        supervisor_context = {
            "message_history": self.context_in.get_message_history()
        }
        
        result = await self.agent_supervisor.run_close(supervisor_context)
        
        # Capturar output do supervisor
        self.agents_params["supervisor"] = {
            "action": "close"
        }
        
        # Adicionar proficiency e skill aos params
        self.agents_params["new_proficiency_level"] = self.context_running.new_proficiency_level
        self.agents_params["new_specific_skill"] = self.context_running.new_specific_skill

        return ChatContextOut(
            supervisor_message=result.output.message,
            params=self.agents_params
        )

    def _error_response(self) -> ChatContextOut:
        """Resposta padrão para erros"""
        logger.error("Gerando resposta de erro")
        return ChatContextOut(
            supervisor_message=(
                "Desculpe, ocorreu um erro interno. Tente novamente."
            ),
            params={}
        )


def create_agent_orquestrator(session: Session) -> AgentOrquestrator:
    """
    Factory function para criar AgentOrquestrator
    
    Args:
        session: Objeto Session do banco (já carregado com skill)
        
    Returns:
        AgentOrquestrator configurado
        
    Exemplo:
        # Buscar session do banco
        session = await session_repo.get_by_id(session_id)
        
        # Criar orquestrador
        orchestrator = create_agent_orquestrator(session)
        
        # Usar
        response = await orchestrator.get_response(user_message)
    """
    return AgentOrquestrator(session)