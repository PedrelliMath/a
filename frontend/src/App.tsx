import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, Plus, Send, Loader2, ChevronLeft, Menu, X, Info, ChevronRight, FileCheck, MessageSquare, CheckCircle2, TrendingUp, ChevronDown, ChevronUp, LogOut, User, AlertCircle } from 'lucide-react';
import { useKeycloak } from './keycloakProvider';
import { useAuthFetch } from './auth-utils';

const API_BASE = 'http://localhost:8000';

// Componente de Alert de Erro
const ErrorAlert = ({ message, onClose }) => {
  if (!message) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md animate-slide-in">
      <div className="bg-red-50 border-l-4 border-red-500 rounded-lg shadow-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-800 mb-1">Erro</h3>
            <p className="text-sm text-red-700">{message}</p>
          </div>
          <button
            onClick={onClose}
            className="text-red-400 hover:text-red-600 transition flex-shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

function App() {
  const { logout, getUserInfo } = useKeycloak();
  const authFetch = useAuthFetch();
  const userInfo = getUserInfo();
  
  const [sessions, setSessions] = useState([]);
  const [skills, setSkills] = useState([]);
  const [evaluations, setEvaluations] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [currentSkill, setCurrentSkill] = useState(null);
  const [progressStructure, setProgressStructure] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [showSkillSelector, setShowSkillSelector] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [paramsOpen, setParamsOpen] = useState(false);
  const [showEvaluation, setShowEvaluation] = useState(false);
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  const [loadingEvaluation, setLoadingEvaluation] = useState(false);
  const [error, setError] = useState(null);
  const [showProgress, setShowProgress] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const messagesEndRef = useRef(null);

  // Hook para tratamento de erros
  const handleError = (err) => {
    let errorMessage = 'Ocorreu um erro inesperado. Tente novamente.';

    if (err?.detail) {
      errorMessage = err.detail;
    } else if (err?.message) {
      errorMessage = err.message;
    } else if (typeof err === 'string') {
      errorMessage = err;
    }

    setError(errorMessage);
    console.error('Erro capturado:', err);
  };

  const clearError = () => {
    setError(null);
  };

  // Monitor de skills
  useEffect(() => {
    console.log('🎯 Estado de skills atualizado:', {
      length: skills.length,
      isArray: Array.isArray(skills),
      skills: skills
    });
  }, [skills]);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => {
        setError(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadCurrentSkill = async (skillId) => {
    try {
      const response = await authFetch(`${API_BASE}/api/v1/skills/${skillId}`);
      const skillData = await response.json();
      setCurrentSkill(skillData);
      
      console.log('Skill carregada:', skillData);
      
      if (skillData.questions && skillData.questions.rubrics) {
        const structure = {};
        const rubrics = skillData.questions.rubrics;
        
        Object.keys(rubrics).forEach(macroName => {
          const bloomLevels = rubrics[macroName];
          let totalQuestions = 0;
          
          Object.keys(bloomLevels).forEach(level => {
            if (Array.isArray(bloomLevels[level])) {
              totalQuestions += bloomLevels[level].length;
            }
          });
          
          const limit = totalQuestions === 1 ? 1 : 2;
          
          structure[macroName] = {
            total: limit,
            answered: 0,
            validated: 0
          };
          
          console.log(`Macro "${macroName}": ${totalQuestions} pergunta(s) total → limite ${limit}`);
        });
        
        console.log('Estrutura de progresso criada:', structure);
        console.log('Macros disponíveis:', Object.keys(structure));
        setProgressStructure(structure);
      }
    } catch (error) {
      console.error('Erro ao carregar skill:', error);
      handleError(error);
    }
  };

  const calculateCurrentProgress = () => {
    if (!progressStructure) return {};
    
    const progress = {};
    Object.keys(progressStructure).forEach(macro => {
      progress[macro] = {
        total: progressStructure[macro].total,
        answered: 0,
        validated: 0
      };
    });
    
    console.log('=== Calculando Progresso ===');
    console.log('Estrutura disponível:', Object.keys(progressStructure));
    
    if (!Array.isArray(messages)) return progress;
    
    messages.forEach((msg, index) => {
      if (msg.user_type === 'bot' && msg.params) {
        const tracker = msg.params.progress_tracker;
        const validator = msg.params.message_validator;
        
        if (tracker && tracker.should_continue === false) {
          const macro = msg.params.new_specific_skill;
          const isValid = validator && validator.is_valid === true;
          
          console.log(`Mensagem #${index} [FINALIZAÇÃO]:`, {
            new_specific_skill: macro,
            should_continue: false,
            isValid,
            validator,
            tracker
          });
          
          if (macro && progress[macro]) {
            if (isValid) {
              progress[macro].validated++;
              progress[macro].answered = Math.min(
                progress[macro].validated,
                progress[macro].total
              );
              console.log(`✓ Validada para ${macro} (finalização): ${progress[macro].answered}/${progress[macro].total}`);
            } else {
              console.log(`✗ Não validada para ${macro} (finalização)`);
            }
          } else if (macro) {
            console.warn(`⚠ Macro "${macro}" não encontrada na estrutura de progresso (finalização)`);
          }
        }
        else if (tracker && tracker.previous_skill) {
          const macro = tracker.previous_skill;
          const isValid = validator && validator.is_valid === true;
          
          console.log(`Mensagem #${index}:`, {
            previous_skill: macro,
            new_skill: tracker.new_skill,
            changed_skill: tracker.changed_skill,
            isValid,
            validator,
            tracker
          });
          
          if (macro && progress[macro]) {
            if (isValid) {
              progress[macro].validated++;
              progress[macro].answered = Math.min(
                progress[macro].validated,
                progress[macro].total
              );
              console.log(`✓ Validada para ${macro}: ${progress[macro].answered}/${progress[macro].total}`);
            } else {
              console.log(`✗ Não validada para ${macro}`);
            }
          } else if (macro) {
            console.warn(`⚠ Macro "${macro}" não encontrada na estrutura de progresso`);
          }
        }
      }
    });
    
    console.log('Progresso final calculado:', progress);
    return progress;
  };

  const ProgressBar = () => {
    if (!progressStructure) return null;
    
    const progress = calculateCurrentProgress();
    const macros = Object.keys(progress).sort();
    
    if (macros.length === 0) return null;
    
    const completedMacros = macros.filter(m => progress[m].answered === progress[m].total).length;
    const totalMacros = macros.length;
    const overallPercentage = totalMacros > 0 ? (completedMacros / totalMacros) * 100 : 0;
    
    return (
      <div className="bg-white border-b border-gray-200">
        <div className="px-4 pt-4 pb-2">
          <button
            onClick={() => setShowProgress(!showProgress)}
            className="w-full flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg hover:from-blue-100 hover:to-green-100 transition-all"
          >
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              <div className="text-left">
                <h3 className="text-sm font-semibold text-gray-800">Progresso por Macro Habilidade</h3>
                <p className="text-xs text-gray-600">
                  {completedMacros} de {totalMacros} concluídas ({Math.round(overallPercentage)}%)
                </p>
              </div>
            </div>
            {showProgress ? (
              <ChevronUp className="w-5 h-5 text-gray-600" />
            ) : (
              <ChevronDown className="w-5 h-5 text-gray-600" />
            )}
          </button>
        </div>

        {showProgress && (
          <div className="px-4 pb-4">
            <div className="max-w-3xl mx-auto space-y-3 pt-3">
              {macros.map(macro => {
                const { total, answered } = progress[macro];
                const percentage = (answered / total) * 100;
                const isComplete = answered === total;
                
                return (
                  <div key={macro} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-700">{macro}</span>
                        {isComplete && (
                          <CheckCircle2 className="w-4 h-4 text-green-600" />
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {answered} / {total} validadas
                      </span>
                    </div>
                    
                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isComplete ? 'bg-green-600' : 'bg-blue-600'
                        }`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-700">Progresso Geral</span>
                  <span className="text-sm font-bold text-gray-700">
                    {Math.round(overallPercentage)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-600 to-green-600 rounded-full transition-all duration-500"
                    style={{ width: `${overallPercentage}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const loadInitialData = async () => {
    console.log('🔄 Iniciando carregamento de dados...');

    // Carrega sessions
    let sessionsData = [];
    try {
      const response = await authFetch(`${API_BASE}/api/v1/sessions/`);
      const data = await response.json();
      sessionsData = Array.isArray(data) ? data : [];
      console.log('✅ Sessions carregadas:', sessionsData.length);
    } catch (error) {
      console.error('❌ Erro ao carregar sessions:', error);
    }

    // Carrega skills
    let skillsData = [];
    try {
      const response = await authFetch(`${API_BASE}/api/v1/skills/`);
      const data = await response.json();
      skillsData = Array.isArray(data) ? data : [];
      console.log('✅ Skills carregadas:', skillsData.length);
    } catch (error) {
      console.error('❌ Erro ao carregar skills:', error);
    }

    // Carrega evaluations (pode não existir)
    let evaluationsData = [];
    try {
      const response = await authFetch(`${API_BASE}/api/v1/evaluations`);
      const data = await response.json();
      evaluationsData = Array.isArray(data) ? data : [];
      console.log('✅ Evaluations carregadas:', evaluationsData.length);
    } catch (error) {
      console.warn('⚠️ Evaluations não encontradas (normal):', error.message);
    }

    console.log('📦 Setando estados:', {
      sessions: sessionsData.length,
      skills: skillsData.length,
      evaluations: evaluationsData.length
    });

    setSessions(sessionsData);
    setSkills(skillsData);
    setEvaluations(evaluationsData);

    console.log('✨ Carregamento concluído');
  };

  const createNewSession = async (skillId) => {
    try {
      console.log('📝 Criando nova sessão com skill:', skillId);
      
      setLoading(true);
      
      const response = await authFetch(`${API_BASE}/api/v1/sessions/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId })
      });

      const newSession = await response.json();
      console.log('✅ Sessão criada:', newSession);
      
      setSessions([newSession, ...(Array.isArray(sessions) ? sessions : [])]);
      
      setCurrentSession(newSession);
      
      setMessages([]);

      setShowSkillSelector(false);
      
      await loadCurrentSkill(skillId);
      
      await loadSessionMessages(newSession.id);
      
      console.log('✨ Sessão criada e carregada com sucesso');
      
    } catch (error) {
      console.error('❌ Erro ao criar sessão:', error);
      handleError(error);
    } finally {
      setLoading(false);
    }
  };

  const loadSessionMessages = async (sessionId) => {
    try {
      const response = await authFetch(`${API_BASE}/api/v1/sessions/${sessionId}/messages`);
      const messagesData = await response.json();
      
      const validMessages = Array.isArray(messagesData) ? messagesData : [];
      setMessages(validMessages);
      
      console.log('Mensagens carregadas:', validMessages);
      
      const hasFinishedMessage = validMessages.some(msg => 
        msg.user_type === 'bot' && 
        msg.params?.progress_tracker?.should_continue === false
      );
      
      if (hasFinishedMessage && !currentEvaluation) {
        await createEvaluationAutomatically(sessionId);
      }
    } catch (error) {
      console.error('Erro ao carregar mensagens:', error);
      handleError(error);
      setMessages([]);
    }
  };

  const createEvaluationAutomatically = async (sessionId) => {
    if (loadingEvaluation) return;
    
    setLoadingEvaluation(true);
    try {
      const getResponse = await authFetch(
        `${API_BASE}/api/v1/evaluations/session/${sessionId}`
      );
      
      if (getResponse.ok) {
        const evaluationData = await getResponse.json();
        setCurrentEvaluation(evaluationData);
      } else {
        const createResponse = await authFetch(
          `${API_BASE}/api/v1/evaluations/session/${sessionId}`,
          { method: 'POST' }
        );

        if (!createResponse.ok) {
          throw new Error('Erro ao criar avaliação');
        }

        const getNewResponse = await authFetch(
          `${API_BASE}/api/v1/evaluations/session/${sessionId}`
        );
        
        const evaluationData = await getNewResponse.json();
        setCurrentEvaluation(evaluationData);
      }
    } catch (error) {
      console.error('Erro ao criar/carregar avaliação:', error);
      handleError(error);
    } finally {
      setLoadingEvaluation(false);
    }
  };

  const selectSession = async (session) => {
    setCurrentSession(session);
    setShowEvaluation(false);
    setCurrentEvaluation(null);
    
    if (!currentSkill || currentSkill.id !== session.skill_id) {
      setCurrentSkill(null);
      setProgressStructure(null);
      await loadCurrentSkill(session.skill_id);
    }
    
    await loadSessionMessages(session.id);
  };

  const createAndLoadEvaluation = async () => {
    if (!currentSession) return;
    
    setLoadingEvaluation(true);
    try {
      const createResponse = await authFetch(
        `${API_BASE}/api/v1/evaluations/session/${currentSession.id}`,
        { method: 'POST' }
      );

      if (!createResponse.ok) {
        throw new Error('Erro ao criar avaliação');
      }

      const getResponse = await authFetch(
        `${API_BASE}/api/v1/evaluations/session/${currentSession.id}`
      );
      
      const evaluationData = await getResponse.json();
      setCurrentEvaluation(evaluationData);
      setShowEvaluation(true);
    } catch (error) {
      console.error('Erro ao criar/carregar avaliação:', error);
      handleError(error);
    } finally {
      setLoadingEvaluation(false);
    }
  };

  const toggleView = () => {
    if (showEvaluation) {
      setShowEvaluation(false);
    } else {
      setShowEvaluation(true);
    }
  };

  const isSessionFinished = () => {
    if (!Array.isArray(messages) || messages.length === 0) return false;
    return messages.some(msg => 
      msg.user_type === 'bot' && 
      msg.params?.progress_tracker?.should_continue === false
    );
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !currentSession || loading || isSessionFinished()) return;

    const userMessage = inputText;
    setInputText('');
    setLoading(true);

    try {
      const response = await authFetch(`${API_BASE}/api/v1/sessions/${currentSession.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userMessage })
      });

      const newMessage = await response.json();
      await loadSessionMessages(currentSession.id);
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      handleError(error);
      setInputText(userMessage);
    } finally {
      setLoading(false);
    }
  };

  const getSkillName = (skillId) => {
    if (!Array.isArray(skills)) return 'Habilidade desconhecida';
    const skill = skills.find(s => s.id === skillId);
    return skill?.name || 'Habilidade desconhecida';
  };

  const getSessionDisplayName = (session) => {
    const skillName = getSkillName(session.skill_id);
    if (!Array.isArray(sessions)) return skillName;
    
    const sessionIndex = sessions
      .filter(s => s.skill_id === session.skill_id)
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
      .findIndex(s => s.id === session.id) + 1;
    return `${skillName} (${sessionIndex})`;
  };

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('pt-BR', { 
        day: '2-digit', 
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Data inválida';
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <ErrorAlert message={error} onClose={clearError} />

      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 bg-white border-r border-gray-200 flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <MessageCircle className="w-6 h-6" />
            Conversas
          </h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          <button
            onClick={() => {
              console.log('🔘 Botão "Novo Chat" clicado. Skills disponíveis:', skills.length);
              setShowSkillSelector(true);
            }}
            className="w-full bg-blue-600 text-white px-4 py-3 rounded-lg hover:bg-blue-700 transition flex items-center justify-center gap-2 font-medium"
          >
            <Plus className="w-5 h-5" />
            Novo Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 space-y-2">
          {Array.isArray(sessions) && sessions.map(session => (
            <button
              key={session.id}
              onClick={() => selectSession(session)}
              className={`w-full text-left p-3 rounded-lg transition ${
                currentSession?.id === session.id
                  ? 'bg-blue-50 border border-blue-200'
                  : 'hover:bg-gray-50 border border-transparent'
              }`}
            >
              <div className="font-medium text-gray-900 truncate">
                {getSessionDisplayName(session)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {formatDate(session.created_at)}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className={`${sidebarOpen ? 'hidden' : 'block'} p-2 hover:bg-gray-100 rounded`}
          >
            <Menu className="w-6 h-6" />
          </button>
          {currentSession && (
            <>
              <div className="flex-1">
                <h1 className="text-xl font-bold text-gray-800">
                  {getSkillName(currentSession.skill_id)}
                </h1>
                <p className="text-sm text-gray-500">
                  Avaliação de Competências
                </p>
              </div>
              {isSessionFinished() && currentEvaluation && (
                <button
                  onClick={toggleView}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center gap-2 font-medium"
                >
                  {showEvaluation ? (
                    <>
                      <MessageSquare className="w-5 h-5" />
                      Ver Mensagens
                    </>
                  ) : (
                    <>
                      <FileCheck className="w-5 h-5" />
                      Ver Avaliação
                    </>
                  )}
                </button>
              )}
              {isSessionFinished() && loadingEvaluation && (
                <div className="px-4 py-2 bg-gray-200 text-gray-600 rounded-lg flex items-center gap-2 font-medium">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Gerando avaliação...
                </div>
              )}
              <button
                onClick={() => setParamsOpen(!paramsOpen)}
                className="p-2 hover:bg-gray-100 rounded-lg transition flex items-center gap-2 text-sm font-medium text-gray-700"
              >
                <Info className="w-5 h-5" />
                Parâmetros
                {paramsOpen ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
              </button>
            </>
          )}
          
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="p-2 hover:bg-gray-100 rounded-lg transition flex items-center gap-2"
            >
              <User className="w-5 h-5 text-gray-700" />
              <span className="text-sm font-medium text-gray-700 hidden md:block">
                {userInfo?.preferred_username || userInfo?.name || 'Usuário'}
              </span>
            </button>
            
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                <div className="px-4 py-3 border-b border-gray-200">
                  <p className="text-sm font-semibold text-gray-800">
                    {userInfo?.name || 'Usuário'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {userInfo?.email || userInfo?.preferred_username}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    logout();
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  Sair
                </button>
              </div>
            )}
          </div>
        </div>

        {currentSession && !showEvaluation && <ProgressBar />}

        <div className="flex-1 overflow-y-auto p-4">
          {!currentSession ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-500">
                <MessageCircle className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium">Nenhuma conversa selecionada</p>
                <p className="text-sm mt-2">Escolha uma conversa ou crie uma nova</p>
              </div>
            </div>
          ) : showEvaluation && currentEvaluation ? (
            <div className="max-w-4xl mx-auto">
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="border-b border-gray-200 pb-4 mb-6">
                  <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
                    <FileCheck className="w-7 h-7 text-green-600" />
                    Avaliação da Sessão
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    ID: {currentEvaluation.id}
                  </p>
                </div>

                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-blue-50 rounded-lg p-4">
                      <p className="text-sm text-blue-600 font-medium mb-1">Usuário</p>
                      <p className="text-lg font-bold text-blue-900">{currentEvaluation.user_id}</p>
                    </div>
                    <div className="bg-green-50 rounded-lg p-4">
                      <p className="text-sm text-green-600 font-medium mb-1">Habilidade</p>
                      <p className="text-lg font-bold text-green-900">{getSkillName(currentEvaluation.skill_id)}</p>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-gray-800 mb-3">Iterações</h3>
                    <div className="space-y-4">
                      {Array.isArray(currentEvaluation.iterations) && currentEvaluation.iterations.map((iteration, index) => (
                        <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                          <div className="flex items-start gap-3 mb-3">
                            <span className="bg-blue-100 text-blue-800 text-xs font-bold px-3 py-1 rounded-full">
                              #{index + 1}
                            </span>
                            {iteration.macro && (
                              <span className="bg-purple-100 text-purple-800 text-xs font-semibold px-3 py-1 rounded-full">
                                {iteration.macro}
                              </span>
                            )}
                          </div>
                          
                          <div className="mb-3">
                            <p className="text-sm font-semibold text-gray-700 mb-1">Pergunta:</p>
                            <p className="text-gray-800">{iteration.question}</p>
                          </div>

                          <div className="mb-3">
                            <p className="text-sm font-semibold text-gray-700 mb-1">Resposta:</p>
                            <p className="text-gray-800">{iteration.response}</p>
                          </div>

                          <div className="grid grid-cols-2 gap-3 mt-4">
                            <div className="bg-yellow-50 rounded p-3">
                              <p className="text-xs text-yellow-700 font-medium mb-1">Nível Esperado</p>
                              <p className="text-sm font-bold text-yellow-900">{iteration.expected_bloom_level}</p>
                            </div>
                            <div className="bg-green-50 rounded p-3">
                              <p className="text-xs text-green-700 font-medium mb-1">Nível Alcançado</p>
                              <p className="text-sm font-bold text-green-900">{iteration.achieved_bloom_level}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-gray-100 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Dados Completos (JSON)</h3>
                    <pre className="text-xs text-gray-800 overflow-x-auto whitespace-pre-wrap break-words bg-white rounded p-3 border border-gray-200">
                      {JSON.stringify(currentEvaluation, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {Array.isArray(messages) && messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.user_type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      message.user_type === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-800'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.text}</p>
                    <p className={`text-xs mt-1 ${
                      message.user_type === 'user' ? 'text-blue-100' : 'text-gray-400'
                    }`}>
                      {formatDate(message.created_at)}
                    </p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                    <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {currentSession && !showEvaluation && !isSessionFinished() && (
          <div className="border-t border-gray-200 bg-white p-4">
            <div className="max-w-3xl mx-auto flex gap-2">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Digite sua mensagem..."
                disabled={loading}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !inputText.trim()}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        )}

        {currentSession && !showEvaluation && isSessionFinished() && (
          <div className="border-t border-gray-200 bg-gray-50 p-4">
            <div className="max-w-3xl mx-auto text-center">
              <div className="inline-flex items-center gap-2 bg-green-100 text-green-800 px-4 py-3 rounded-lg">
                <FileCheck className="w-5 h-5" />
                <span className="font-medium">Sessão finalizada! Clique em "Ver Avaliação" para visualizar o resultado.</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className={`${paramsOpen ? 'w-96' : 'w-0'} transition-all duration-300 bg-white border-l border-gray-200 flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <Info className="w-5 h-5" />
            Parâmetros das Mensagens
          </h2>
          <button
            onClick={() => setParamsOpen(false)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {Array.isArray(messages) && messages.map((message, index) => (
            <div key={message.id} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-xs font-semibold px-2 py-1 rounded ${
                  message.user_type === 'user' 
                    ? 'bg-blue-100 text-blue-800' 
                    : 'bg-green-100 text-green-800'
                }`}>
                  {message.user_type === 'user' ? 'Usuário' : 'Assistente'}
                </span>
                <span className="text-xs text-gray-500">#{index + 1}</span>
              </div>
              
              <div className="text-xs text-gray-600 mb-2 truncate">
                {message.text.substring(0, 50)}...
              </div>

              {message.params && Object.keys(message.params).length > 0 ? (
                <div className="bg-white rounded border border-gray-200 p-2">
                  <pre className="text-xs text-gray-800 overflow-x-auto whitespace-pre-wrap break-words">
                    {JSON.stringify(message.params, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="text-xs text-gray-400 italic">
                  Sem parâmetros
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {showSkillSelector && (() => {
      console.log('🎨 Modal renderizando. Estado:', {
        showSkillSelector,
        skillsLength: skills.length,
        skillsIsArray: Array.isArray(skills),
        skills: skills
      });
      return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-gray-800">
                Selecione uma Habilidade ({skills.length} disponíveis)
              </h2>
              <button
                onClick={() => setShowSkillSelector(false)}
                disabled={loading}
                className="p-2 hover:bg-gray-100 rounded-lg transition disabled:opacity-50"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {/* ADICIONE OVERLAY DE LOADING */}
            {loading && (
              <div className="absolute inset-0 bg-white bg-opacity-90 flex items-center justify-center z-10">
                <div className="text-center">
                  <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
                  <p className="text-lg font-semibold text-gray-800">Iniciando sessão...</p>
                  <p className="text-sm text-gray-600 mt-2">Aguarde enquanto preparamos tudo</p>
                </div>
              </div>
            )}
            
            <div className="p-6 overflow-y-auto max-h-[calc(80vh-100px)]">
              {!Array.isArray(skills) ? (
                <div className="text-center py-8 text-red-600">
                  <p>Erro: skills não é um array</p>
                  <p className="text-xs mt-2">Tipo: {typeof skills}</p>
                </div>
              ) : skills.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500 mb-4">Nenhuma habilidade disponível</p>
                  <button
                    onClick={() => {
                      console.log('🔄 Recarregando dados...');
                      loadInitialData();
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Tentar novamente
                  </button>
                </div>
              ) : (
                <div className="grid gap-4">
                  {skills.map((skill, index) => {
                    console.log(`🎯 Renderizando skill #${index}:`, skill);
                    return (
                      <button
                        key={skill.id}
                        onClick={() => {
                          console.log('✅ Skill selecionada:', skill);
                          createNewSession(skill.id);
                        }}
                        disabled={loading}
                        className="text-left p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <h3 className="font-bold text-lg text-gray-800">{skill.name}</h3>
                        <p className="text-sm text-gray-600 mt-1">{skill.description}</p>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    })()}
    </div>
  );
}

export default App;