# Roadmap de melhorias — Koru

Documento de trabalho. Deriva de `docs/koru-v2-spec.md`, mas não é a spec: aqui só entra o que
foi **verificado no código atual**, com caminho de arquivo e critério de aceite.

Referência de leitura obrigatória antes de mexer em qualquer coisa estrutural: `docs/koru-v2-spec.md`.
Os princípios P1–P8 (spec §2) valem como critério de rejeição de PR.

---

## Como este roadmap é organizado

A spec descreve o destino (v2) e as correções imediatas (§15). Este roadmap organiza o caminho em
**ondas**, ordenadas por uma regra só: *informação destruída hoje é irrecuperável amanhã*.

Toda sessão que roda agora perde permanentemente o `skill_analysis` por competência. Isso põe as
ondas 1 e 2 antes de qualquer reconstrução: elas são baratas e param a sangria enquanto o v2 é
construído em paralelo.

| Onda | Tema | Bloqueia | Status |
|---|---|---|---|
| 0 | Higiene, verificação e código morto | tudo | **aplicada** |
| 1 | Parar de destruir evidência | Fase 3 da spec | **aplicada** |
| 2 | Justiça estrutural barata | nada | **parcial** |
| 3 | Corretude de runtime | produção | pendente |
| 4 | Rubrica e golden set (spec Fases 0–3) | Fase 4 | pendente |
| 5 | Estado explícito e grafo (spec Fase 4) | Fases 5–7 | pendente |
| 6 | Item bank fixo e supervisor (spec Fases 2, 5) | Fase 7 | pendente |
| 7 | Auditoria, LGPD e calibração (spec Fases 6–7) | — | pendente |

---

## Estado atual verificado

Levantamento feito lendo o repositório, não a spec. Cada linha tem endereço.

### O que funciona e deve sobreviver

- **Separação parcial LLM/código.** O fine-tune devolve nível de Bloom por habilidade;
  `compare_bloom_levels` e a agregação são código puro
  (`src/app/ai/agents/skill_evaluator.py:243`). É a semente de P1.
- **`end_prompt` do supervisor** (`src/app/ai/agents/prompts/supervisor.py:37`). Postura avaliativa
  neutra calibrada. Anti-requisito da spec: não reescrever.
- **Avaliação por habilidade individual já existe.** `skill_analysis` é produzido em
  `skill_evaluator.py:363` com nível por competência.
- **`justification_system_prompt_template`** (`prompts/skill_evaluator.py:8`) já exige citação de
  trecho e proíbe tautologia. É o mais próximo de rubrica que existe no sistema.

### O que está quebrado (verificado)

| # | Onde | O quê |
|---|---|---|
| B1 | `services/agent_orquestrator.py:554` | `_generate_supervisor_response` definido duas vezes; a primeira é copy-paste do `_handle_skip` e referencia `current_level`/`current_skill` fora de escopo. Python usa a segunda; a primeira nunca roda e nunca rodaria. |
| B2 | `ai/agents/helpers/state_initializer.py:1` | importa `app.db.models` e `app.agents.schemas.agents.graph.state`, inexistentes. ImportError garantido. |
| B3 | `ai/agents/skill_evaluator.py:545` | bloco `return Output(...)` inalcançável, depois do `return`/`except` de `_generate_skill_justifications`. |
| B4 | `prompts/supervisor.py:31` + `supervisor.py:44` | `_handle_invalid_message` gera uma pergunta reformulada com LLM (`_regenerate_question`) e **joga fora**: `retype_prompt` só interpola `{message_history}`. Uma chamada de LLM paga por resposta inválida, descartada. |
| B5 | `services/session.py:244`, `services/evaluation.py:219` | passam `UUID` para `repository.delete()`, que espera a entidade ORM. `db.delete(UUID)` estoura. `DELETE /sessions/{id}` e `DELETE /evaluations/{id}` estão quebrados. |
| B6 | `services/session.py:73`, `:255`, `:265` | `has_owned_resource(session, ...)` é chamado **antes** do teste `if not session`. Sessão inexistente vira `AttributeError`/500 em vez de 404. |
| B7 | `repository/session.py:52` | `add_message` faz read-modify-write do JSONB inteiro sem lock. Duas mensagens simultâneas do mesmo candidato perdem uma. |
| B8 | `models/evaluation.py:38` | `EvaluationOutput.iterations: dict`, mas a coluna e o valor são `list`. Schema mente. |
| B9 | `services/agent_orquestrator.py:181` | `except Exception` genérico devolvendo "Desculpe, ocorreu um erro interno". Viola P8 diretamente. Mesmo padrão em `skill_evaluator.py:487` e `services/session.py`. |
| B10 | `main.py:35` | `Base.metadata.create_all` no lifespan, sem Alembic. Não há migração; as tabelas novas da spec §9 não têm por onde entrar. |
| B11 | `skill_evaluator.py:82` | I/O de disco síncrono + pandas dentro do caminho async de request, gravando em `artifacts/` — que é efêmero. O `skill_analysis` estruturado só existe ali e some no deploy. |
| B12 | `updateskill.json` | O banco está **pior do que a spec descreve**. `scripts/validate_question_bank.py` mede: 22 das 24 células estão abaixo do mínimo de 3 itens da spec §4.1. "Autoconhecimento" tem 1 item por nível nos 6 níveis; os outros 3 blocos têm 2 em quase toda célula. Só 2 células no banco inteiro atendem ao mínimo. Skip e reformulação não têm item alternativo em lugar nenhum. |
| B13 | `services/agent_orquestrator.py:232` | `available_skills[0]` — todo candidato começa no mesmo bloco, sistematicamente penalizado pelo efeito de primeira resposta. |
| B14 | repositório | nenhum teste, nenhum linter, nenhum CI. P7 ("nada é medido sem ser medível") não tem como ser cumprido. |
| B15 | `.DS_Store` × 6 | versionados apesar do `.gitignore`. |
| B16 | `config.py:52` + `agent_orquestrator.py:145` | `openai_api_key` existe em `Settings` mas o avaliador lê `os.getenv("OPENAI_API_KEY")` direto. Dois caminhos de configuração para a mesma credencial. |
| B17 | `config.py:133` + `database/db.py:8` | `settings = Settings()` e `create_engine(...)` rodam **em tempo de import**. Importar qualquer módulo de `app` exige a configuração inteira, credenciais inclusive, e abre um engine de banco. Foi o que impediu qualquer teste de existir. Contornado por `tests/conftest.py`; a correção é settings preguiçoso/injetado. |
| B18 | `config.py:73`, `:77` | `helicone_api_key` e `openai_api_key` declarados `SecretStr = Field(default=None)`. `SecretStr` não aceita `None`: o default nunca funciona e as duas variáveis são, na prática, obrigatórias. |
| B19 | `observability/helicone_decorator.py:117` | a exceção era capturada em `error` e nunca usada. Chamada de agente que falha ficava indistinguível de uma bem-sucedida na observabilidade. |

### Os problemas estruturais (spec §1.2)

Estes não são bugs, são consequências do desenho. Só saem nas ondas 4–6.

- **Pr1. Não existe rubrica.** `skill.questions.rubrics` é `bloco → nível → lista de perguntas`.
  Sem critério, sem gate, sem escala. Verificado em `updateskill.json`.
- **Pr2. Informação destruída todo turno.** O avaliador produz nível por habilidade; a votação por
  maioria (`skill_evaluator.py:406`) colapsa em um `int` de -1 a 1. O detalhe só sobrevive em CSV local.
- **Pr3. O avaliador não vê a pergunta.** `dados_classificacao = {"habilidades_macro": [...]}`
  (`skill_evaluator.py:359`). O enunciado é recebido e ignorado.
- **Pr4. Candidatos não são comparáveis.** Perguntas geradas em runtime com `temperature=0.3`.
- **Pr5. Viés de registro verbal.** Nunca foi medido.

---

## Onda 0 — Higiene, verificação e código morto ✅

Barato, sem risco, destrava tudo que vem depois. O ponto não é a limpeza: é que sem teste e sem CI
nenhuma afirmação de qualidade das ondas seguintes pode ser verificada (P7).

- [x] Remover a duplicata de `_generate_supervisor_response` (B1) — spec C4
- [x] Deletar `helpers/state_initializer.py` (B2) — spec C5
- [x] Remover o `return` inalcançável do avaliador (B3)
- [x] Aproveitar a pergunta reformulada no `retype_prompt` (B4)
- [x] Registrar em log a falha de agente que era engolida na observabilidade (B19)
- [x] Remover 35 imports mortos apontados pelo lint
- [x] Destrackear os `.DS_Store` (B15)
- [x] `pytest` + `ruff` como dev deps, suíte de testes das funções puras (B14)
- [x] CI rodando lint + testes em todo push/PR (B14)
- [x] `scripts/check_verbosity_bias.py` (spec C3, P7)
- [x] `scripts/validate_question_bank.py` — detecta células com menos de 3 itens (spec C6, P7)

**Aceite:** `pdm run test` (31 testes) e `pdm run lint` passam; CI verde. O
`validate_question_bank.py` **falha de propósito**: o banco está mesmo incompleto, e é isso que
ele existe para mostrar. No CI ele roda como informativo, para não travar merge por um problema
de conteúdo — mas fica visível em todo build.

**Sobre `check_verbosity_bias.py`:** roda, mas com os dados versionados no repositório encontra
**1 par**. Ele se recusa a concluir qualquer coisa abaixo de 20 pares, em vez de imprimir um
número sem significado. Para responder a pergunta de fato, apontar `--dir` para os artefatos de
observabilidade reais. Isso continua sendo a primeira medição a fazer (spec C3).

## Onda 1 — Parar de destruir evidência ✅

A onda mais urgente do roadmap. Cada dia que passa sem ela é um dia de sessões cujo dado por
competência é perdido para sempre. Não depende de nenhuma decisão pendente.

- [x] **C1 — Persistir `skill_analysis` estruturado.** O nível por competência passa a ir para
  `params["skill_evaluator"]["skill_analysis"]` e daí para `evaluations.iterations`, em vez de
  virar a string `"skill:0, skill:1"`.
- [x] **C2 — Passar o enunciado ao avaliador.** `dados_classificacao` passa a levar `pergunta`
  junto de `habilidades_macro`. Corrige Pr3 e é pré-requisito para aposentar o `message_validator`.

**Aceite:** uma sessão completa produz, em `evaluations.iterations`, um registro por turno com
`skill_analysis` contendo `skill`, `expected_bloom_level`, `achieved_bloom_level` e `adequacao`.
Nenhuma informação do avaliador depende mais do CSV em `artifacts/`.

**Nota sobre C2 e o fine-tune.** O modelo `bloom-evaluator` foi treinado com um payload que não
tinha `pergunta`. Acrescentar o campo muda a distribuição de entrada. O comportamento observado
precisa ser conferido contra respostas conhecidas antes de ir para produção — e é exatamente
o que o golden set da Onda 4 vai permitir medir. Até lá, tratar como mudança sob observação.

## Onda 2 — Justiça estrutural barata 🟡

Medidas da spec §6.1 que não dependem do item bank. São as que dão mais justiça por linha de código.

- [x] **C7 — Randomizar a ordem dos blocos** com seed determinística derivada do `session_id`.
  Reprodutível, auditável, e elimina a penalidade fixa do primeiro bloco (B13).
- [ ] **C6 — Preencher as células vazias do banco** (B12). *Bloqueado: autoria de conteúdo.*
  `validate_question_bank.py` já aponta o que falta. Escrever item de avaliação é decisão de
  conteúdo do time — não deve ser gerado por agente sem revisão humana, porque o item é o
  instrumento de medição.
- [ ] **Item de aquecimento.** O primeiro item da sessão não pontua. Elimina, para todos
  igualmente, a penalidade da primeira resposta. Depende de C6 para ter item sobrando.
- [ ] **D2 — Orçamento em itens, não em minutos.** Hoje `expiration_at` vem de
  `duration_minutes` (`services/session.py:56`). Limite de tempo favorece quem digita rápido, o que
  é variância irrelevante ao construto. Manter tempo só como timeout operacional generoso.
  *Bloqueado: decisão do time.*

**Aceite de C7:** duas sessões da mesma skill com `session_id` diferentes começam em blocos
diferentes; a mesma `session_id` sempre produz a mesma ordem (teste automatizado).

## Onda 3 — Corretude de runtime

Bugs que quebram endpoints ou corrompem dados. Independentes do v2 — valem mesmo que a
reconstrução seja abandonada.

- [ ] B5 — corrigir as chamadas de `delete` (passar entidade, não UUID) + teste de regressão
- [ ] B6 — checar `if not session` antes de `has_owned_resource` em todos os serviços
- [ ] B7 — `SELECT ... FOR UPDATE` na sessão no início do turno (spec §9)
- [ ] B8 — `EvaluationOutput.iterations: list[dict]`
- [ ] B10 — introduzir Alembic; parar de criar schema por `create_all`
- [ ] B11 — tirar o I/O de artefatos do caminho de request (o dado já vai para o banco pela Onda 1)
- [ ] B16 — credencial da OpenAI só via `settings`
- [ ] B17 — settings e engine deixam de ser instanciados em tempo de import (destrava testar
      qualquer coisa que toque `app.config`, e remove o `conftest.py` de contorno)
- [ ] B18 — `helicone_api_key` e `openai_api_key` com tipo honesto (`SecretStr | None`)
- [ ] B9 — remover os `except Exception` que devolvem mensagem cordial (P8). **Fazer por último
  nesta onda:** hoje eles escondem os bugs acima; tirar antes de corrigi-los troca 500 silencioso
  por 500 barulhento sem ganho.

**Aceite:** `DELETE /sessions/{id}` e `DELETE /evaluations/{id}` respondem 204; sessão inexistente
responde 404; teste de concorrência com duas mensagens simultâneas não perde nenhuma; `alembic
upgrade head` reproduz o schema do zero.

## Onda 4 — Rubrica e golden set (spec Fases 0–3)

O coração do problema. Sem rubrica, "boa evidência" é intuição individual e um resultado
contestado não tem defesa.

- [ ] **Fase 0 — exercício de ancoragem** (spec §12.1). Sem código, custa uma tarde: 20
  transcrições, 3 pessoas marcando onde teriam mudado de assunto, sem discutir entre si.
  Resolve D3 e produz o golden set inicial.
- [ ] `domain/evidence.py` — `Evidencia`, `EvidenciaCriterio`, `AntiCriterioDetectado`
- [ ] `domain/items.py` — `Criterio` com `evidencia_gate` escrito a partir da Fase 0
- [ ] Migrar `AgentSkillEvaluator` do cliente OpenAI direto para `Agent` do Pydantic AI com
  `output_type=Evidencia` (com cuidado: o fine-tune continua sendo o modelo)
- [ ] `validar_evidencia` — trecho citado que não existe na resposta zera o score (P2)
- [ ] Anotar 100 casos; suite `pydantic_evals` em `evals/`

**Aceite (spec Fase 3):** concordância adjacente > 0.85; taxa de trecho alucinado < 0.05;
`check_verbosity_bias.py` < 0.4.

**Antes de escrever o agente:** instalar a skill oficial do Pydantic AI. A API mudou na v2 e o
código atual usa a antiga. Não escrever de memória.

## Onda 5 — Estado explícito e grafo (spec Fase 4)

- [ ] `domain/state.py` — `AssessmentState` como única fonte de verdade (P3)
- [ ] `engine/progression.py` — `decidir_proximo_passo(estado, evidencia) -> Decisao`, a fronteira
      estável entre a regra v2.0 (concordância) e a v2.1 (erro padrão / IRT)
- [ ] `engine/agreement.py` — regra de concordância da spec §5.1
- [ ] Tabelas `assessment_states`, `turns`, `evidence_scores` (spec §9), append-only
- [ ] Grafo com `pydantic_graph`; `docs/graph.md` gerado e verificado no CI
- [ ] `POST /sessions/{id}/reprocess` — recomputa sem LLM

**Aceite:** sessão completa ponta a ponta; `/reprocess` reproduz o resultado sem nenhuma chamada de
LLM. Se `/reprocess` não funciona, P5 falhou e a arquitetura falhou junto.

**Substitui:** `count_messages >= 2` como regra de parada, e a reconstrução de estado varrendo
`session.messages` (`agent_orquestrator.py:203`).

## Onda 6 — Item bank fixo e supervisor (spec Fases 2, 5)

- [ ] `bank/` com itens versionados, 3 por célula, formatos variados, 3–4 âncoras
- [ ] `bank/validate.py` (sucessor de `scripts/validate_question_bank.py`)
- [ ] Remover `question_generator.py` — geração em runtime viola P6 e causou o efeito formulário
- [ ] Remover `message_validator.py` — absorvido por `Evidencia.respondeu_a_pergunta`
- [ ] Remover `helpers/transition_phrases.py` — `ponto_forte_anterior` torna a frase sorteada
      desnecessária, e lista finita o usuário detecta rápido
- [ ] Supervisor apresenta o enunciado fixo; evidência do turno anterior chega a ele

De 4 chamadas de LLM por turno para 2.

**Aceite:** 10 sessões manuais sem repetição de estrutura perceptível; tempo até primeiro token
abaixo de 1.5s.

## Onda 7 — Auditoria, LGPD e calibração (spec Fases 6–7)

- [ ] `GET /admin/sessions/{id}/audit`, `POST /admin/turns/{id}/human-review`
- [ ] `avaliacao_humana` migra do CSV para `evidence_scores`
- [ ] Spans OTel e alertas (spec §11)
- [ ] Após ~200 sessões: `calibrate_difficulty.py`, `validate_bloom_ladder.py`, `check_dif.py`
- [ ] Migrar `progression.py` para a regra v2.1

**Não implementar IRT antes de ter os dados.** Sem ~200 sessões, o modelo é enfeite.

---

## Decisões pendentes

Bloqueiam ondas específicas. Não devem ser resolvidas com valor default.

| # | Decisão | Recomendação da spec | Bloqueia |
|---|---|---|---|
| D1 | Granularidade da competência | blocos para navegação, theta por competência individual | Onda 5 |
| D2 | Orçamento: minutos ou itens | itens | Onda 2 |
| D3 | Onde fica o corte de evidência suficiente | não decidir por opinião — rodar §12.1 primeiro | Onda 4 |

Uma pergunta adicional, fora da spec: **auditar o dado de treino do fine-tune** (spec §6.2,
mitigação 4). Se o conjunto que ensinou o `bloom-evaluator` o que é "analisar" era homogêneo em
escolaridade ou área, o viés está nos pesos e nenhum prompt corrige. Vale saber antes de investir
na Onda 4.

---

## O que este roadmap não faz

- Não migra sessões v1. Não existe evidência estruturada nem critério nelas, só um `classificacao`
  de -1 a 1. Ficam somente-leitura, com resultado congelado e marcação explícita de metodologia v1.
- Não reescreve o `end_prompt` do supervisor.
- Não gera itens de avaliação automaticamente. O item é o instrumento de medição; conteúdo novo
  passa por revisão humana.
