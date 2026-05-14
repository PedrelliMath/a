# Fluxo atual do Skill Valuator

Este documento descreve, em detalhes, como o Skill Valuator funciona hoje no projeto, desde a chamada da API ate a persistencia dos resultados.

## Visao geral

O Skill Valuator e um agente que:

1. Recebe a resposta do usuario.
2. Classifica o nivel de Bloom por habilidade individual dentro da macrocompetencia atual.
3. Gera uma classificacao macro `-1 | 0 | 1`.
4. Atualiza o nivel de proficiencia da conversa.
5. Exporta artefatos de observabilidade para auditoria.

Ele roda dentro do `AgentOrquestrator`, junto com `message_validator`, `question_generator` e `supervisor`.

## Onde o fluxo comeca

O fluxo de avaliacao acontece no endpoint de mensagens da sessao:

1. `POST /api/v1/sessions/{session_id}/messages`
2. O service salva a mensagem do usuario.
3. O service instancia o orquestrador e chama `get_response(user_message)`.
4. O orquestrador executa o pipeline.
5. A resposta do bot e salva com `params` (inclui outputs dos agentes, inclusive o valuator).

Arquivos principais:

- `src/app/routers/session.py`
- `src/app/services/session.py`
- `src/app/ai/agents/services/agent_orquestrator.py`

## Inicializacao do Skill Valuator

Na inicializacao dos agentes (`_init_agents`), o orquestrador le:

- `skill.agents_config.skill_evaluator.model_name`
- `skill.agents_config.skill_evaluator.temperature`

Com isso ele cria `AgentSkillEvaluator` com:

- `model_id`: ID do modelo fine-tunado (ou fallback)
- `system_prompt_template`: prompt em `prompts/skill_evaluator.py`
- `api_key`: `OPENAI_API_KEY`
- `base_url`: configurado se Helicone estiver ativo

Arquivo principal:

- `src/app/ai/agents/services/agent_orquestrator.py`

## Ordem completa do pipeline (mensagem valida)

Quando o usuario envia uma mensagem, o `AgentOrquestrator` executa esta sequencia:

1. Valida mensagem (`_validate_message`).
2. Se invalida: regenera pergunta e retorna feedback (nao avalia Bloom).
3. Se valida: executa Skill Valuator (`_evaluate_response`).
4. Atualiza progresso (`_update_progress`): pode trocar macrocompetencia.
5. Gera nova pergunta (`_generate_question`).
6. Supervisor entrega mensagem final.

Ponto importante:

- O Skill Valuator roda apenas no caminho de mensagem valida.

## Contexto enviado para o Skill Valuator

No metodo `_evaluate_response`, o orquestrador monta `evaluation_context` com:

- `user_message`
- `question` (ultima pergunta do bot)
- `current_proficiency_level`
- `current_specific_skill` (macrocompetencia atual)
- `current_question_set`
- `rubrics`
- `bloom_levels`
- `session` (para usar `session_id` na auditoria)

Arquivo:

- `src/app/ai/agents/services/agent_orquestrator.py`

## O que o Skill Valuator faz internamente

Classe principal:

- `AgentSkillEvaluator` em `src/app/ai/agents/skill_evaluator.py`

### 1) Preparacao de habilidades individuais

A macrocompetencia (string com itens separados por virgula) e transformada em lista de habilidades normalizadas:

- quebra por virgula
- lowercase
- remove acentos
- substitui espacos por `_`

Exemplo:

- `"Dados e Inteligencia Artificial, Solucao de Problemas"`
- vira `['dados_e_inteligencia_artificial', 'solucao_de_problemas']`

### 2) Montagem do prompt do modelo

O sistema usa `system_prompt_template` e injeta `dados_classificacao` com:

- `habilidades_macro`: lista normalizada

Depois envia:

- role `system`: prompt com habilidades esperadas
- role `user`: resposta textual do usuario

A chamada usa `chat.completions.create` com:

- `model=self.model_id`
- `temperature=self.temperature`

### 3) Parse da resposta do modelo

O parser tenta, nesta ordem:

1. JSON com chave `habilidades`:
   - ex.: `{ "habilidades": { "colaboracao": "analisar" } }`
2. JSON simples `{ skill: nivel }`
3. Heuristica textual (`skill:nivel` separado por `,`, `;` ou quebra de linha)

Resultado do parse:

- `achieved_levels: dict[str, str]`

### 4) Comparacao Bloom (esperado vs obtido)

Para cada habilidade individual:

1. Pega nivel esperado atual (`current_proficiency_level`).
2. Pega nivel obtido pelo modelo.
3. Compara usando ordem Bloom fixa:
   - lembrar < compreender < aplicar < analisar < avaliar < criar

Regra da funcao `compare_bloom_levels`:

- `-1`: abaixo do esperado
- `0`: igual ao esperado
- `1`: acima do esperado

Detalhe importante:

- Se o modelo retornar multiplos niveis (`"avaliar/criar"`), o codigo escolhe o nivel mais proximo do esperado.

### 5) Calculo da classificacao macro

Depois de classificar cada habilidade, o agente faz voto majoritario entre `-1, 0, 1`.

Desempate (como esta no codigo hoje):

1. prefere `0`
2. se nao houver `0`, prefere `-1`
3. senao usa `1`

Saidas finais do valuator:

- `classificacao` (int): `-1 | 0 | 1`
- `adequacao_habilidades` (string): ex. `"empatia:0, colaboracao:1"`
- `adequacao_macro` (string): `"-1" | "0" | "1"`

## Como isso altera o nivel da conversa

No orquestrador, apos `run_evaluation`:

1. Le `classificacao`.
2. Se `classificacao != 0`, chama `get_proficiency_level`.
3. Move um nivel por vez para cima ou para baixo.
4. Atualiza `context_running.new_proficiency_level`.

Exemplo:

- esperado `analisar`
- classificacao `1`
- novo nivel `avaliar`

## Troca de macrocompetencia

Depois da avaliacao, `_update_progress` decide se troca de macrocompetencia:

1. Conta quantas perguntas validas ja foram feitas para a macro atual.
2. Se `count_messages >= 2`, muda para a proxima macro da lista.
3. Ao trocar macro, reseta proficiencia para `analisar`.
4. Se nao houver proxima macro, encerra o fluxo (`should_continue = False`).

## O que vai para `params` da mensagem do bot

No final da iteracao, o bot salva no historico algo neste formato:

```json
{
  "message_validator": {
    "is_valid": true,
    "feedback": "..."
  },
  "skill_evaluator": {
    "classification": 1,
    "adequacao_habilidades": "...",
    "adequacao_macro": "1",
    "expected_level": "analisar",
    "achieved_level": "avaliar"
  },
  "progress_tracker": {
    "should_continue": true,
    "previous_skill": "...",
    "new_skill": "...",
    "changed_skill": false
  },
  "question_generator": {
    "question": "...",
    "action": "generate"
  },
  "supervisor": {
    "action": "end"
  },
  "new_proficiency_level": "avaliar",
  "new_specific_skill": "..."
}
```

Esse `params` e persistido em `session.messages` (JSONB) e reaproveitado em fluxos posteriores.

## Observabilidade e artefatos do Skill Valuator

O valuator registra metadados em disco por sessao:

Pasta base:

- `artifacts/observability/skill_evaluator/{session_id_sanitizado}`

Arquivos gerados/atualizados:

1. `skill_evaluator_detail.json`
   - historico completo por iteracao
   - prompt, resposta bruta, parse, classificacao, modelo, temperatura, etc.
2. `skill_evaluator.csv`
   - linhas para analise tabular
3. `skill_evaluator_cleaned.csv`
   - versao expandida e normalizada para analise

Variavel de ambiente para mudar destino:

- `SKILL_EVALUATOR_OBSERVABILITY_DIR`

## Integracao com Helicone

- `run_evaluation` usa `@track_helicone(agent_type="skill_evaluator")`.
- O orquestrador abre `HeliconeContext(session_id, user_id)` no `get_response`.
- Se configurado, `base_url` da OpenAI aponta para proxy Helicone.

## Como o modulo de Evaluation consome esse resultado

Ao criar avaliacao final de sessao, o service percorre mensagens e extrai iteracoes.

Campo usado para nivel obtido:

1. `params.skill_evaluator.achieved_level`
2. fallback: `params.new_proficiency_level`

Arquivo:

- `src/app/services/evaluation.py`

## Resumo tecnico rapido

1. Usuario responde.
2. Message validator aprova/reprova.
3. Se aprovada, Skill Valuator classifica Bloom por habilidade.
4. Orquestrador atualiza nivel (subir/descer/manter).
5. Progress tracker decide troca de macro a cada 2 perguntas validas.
6. Question generator cria proxima pergunta.
7. Supervisor entrega texto final.
8. Tudo fica salvo em `session.messages[].params`.
9. Skill Valuator exporta artefatos de auditoria em `artifacts/observability`.
