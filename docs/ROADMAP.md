# Roadmap — Koru v2

Plano de execução de `docs/koru-v2-spec.md`. A spec descreve o destino e a §14 define a ordem;
este documento é o mesmo caminho com status, endereço no código e bloqueio explícito por etapa.

**A espinha dorsal são as Fases 0–7 da spec §14, e a ordem é obrigatória.** Não há atalho: cada
fase existe porque a seguinte depende do aceite dela. Pular a Fase 0 significa escrever rubrica por
intuição; pular a Fase 2 significa medir com instrumento que não existe.

Os princípios P1–P8 (§2) valem como critério de rejeição de PR, em qualquer fase.

---

## Onde estamos

| Etapa | Situação |
|---|---|
| §15 Correções imediatas | 5 de 7 aplicadas |
| Fase 0 — Ancoragem | **não iniciada — é o gargalo** |
| Fases 1–7 | não iniciadas |
| Decisões D1, D2, D3 | as três em aberto |

Nenhuma fase do v2 começou. O que foi feito até aqui é a §15, que por definição **não espera** pela
reconstrução, mais a infraestrutura de verificação que o P7 exige para qualquer afirmação de
qualidade ser checável.

### Os princípios hoje

| | Princípio | Situação |
|---|---|---|
| P1 | O LLM observa, o código decide | 🟡 a agregação é código, mas o agente ainda devolve nível e a progressão é voto de maioria |
| P2 | Toda afirmação avaliativa cita a fonte | ❌ o prompt pede trecho; nada verifica em código |
| P3 | O estado é explícito e persistido | ❌ estado ainda é derivado varrendo `session.messages` |
| P4 | A rubrica nunca chega ao gerador | ⚪ vale por vacuidade — não existe rubrica |
| P5 | Reprocessamento sem LLM | ❌ mas o C1 é o pré-requisito: agora existe o que reprocessar |
| P6 | Mesmo estímulo na mesma posição | ❌ `question_generator` gera em runtime a `temperature=0.3` |
| P7 | Nada é medido sem ser medível | 🟡 CI, 31 testes e 2 dos 6 scripts |
| P8 | Falha explícita | ❌ 23 `except Exception` no código |

---

## Pré-fase — §15 Correções imediatas

Não esperam pelo v2 e valem mesmo que a reconstrução seja adiada.

| | Correção | Situação |
|---|---|---|
| C1 | Persistir `skill_analysis` em vez do voto | ✅ aplicada |
| C2 | Passar `question` ao avaliador | ✅ aplicada, sob observação |
| C3 | Rodar `check_verbosity_bias.py` nos dados existentes | 🟡 **ferramenta existe, medição não aconteceu** |
| C4 | Remover a duplicata de `_generate_supervisor_response` | ✅ aplicada |
| C5 | Deletar `helpers/state_initializer.py` | ✅ aplicada |
| C6 | Preencher as células vazias do banco | ❌ bloqueada em autoria de conteúdo |
| C7 | Randomizar a ordem dos blocos | ✅ aplicada |

**C3 é a pendência que mais incomoda.** O script roda, mas encontra 1 par nos dados versionados e
se recusa a concluir abaixo de 20 — a pergunta que ele existe para responder (*o avaliador lê
complexidade cognitiva ou sofisticação verbal?*) segue sem resposta. Só falta apontar `--dir`
para os artefatos de observabilidade reais. É a medição mais barata e mais séria que resta.

**Sobre C2.** O fine-tune `bloom-evaluator` foi treinado com um payload sem `pergunta`.
Acrescentar o campo muda a distribuição de entrada. O efeito só é mensurável com o golden set da
Fase 3 — até lá, mudança sob observação.

**Sobre C6.** `scripts/validate_question_bank.py` mede a lacuna: **22 das 24 células** estão abaixo
do mínimo de 3 itens da §4.1, não apenas "Autoconhecimento" como a spec supunha. Só 2 células no
banco inteiro atendem. Autoria de item é decisão de conteúdo — o item é o instrumento de medição,
e não deve ser gerado por agente sem revisão humana. A Fase 2 absorve isso.

---

## Fase 0 — Exercício de ancoragem

**Sem código.** Custa uma tarde e é o gargalo de tudo que vem depois.

1. Selecionar 20 transcrições reais de sessões já rodadas.
2. Pedir a três pessoas do time que marquem, em cada uma, **em que ponto teriam mudado de assunto**.
   Sem discutir entre si.
3. Comparar as marcações.

Se concordam na maioria dos casos, o que as respostas marcadas têm em comum — exemplo específico,
resultado mensurável, decisão justificada — vira o texto dos `evidencia_gate`.

Se discordam muito, **o problema não é o algoritmo.** Nenhuma regra de parada satisfaz um time que
não concorda sobre o que é evidência suficiente, e a conversa que precisa acontecer é sobre a
rubrica, não sobre código.

**Aceite (spec §14):** `evidencia_gate` escrito para pelo menos um bloco, e a decisão D3 tomada
com base em dados.

**Produz:** o golden set inicial (transcrições já vêm com julgamento humano anexado) e a resposta
de D3.

**Bloqueia:** Fases 1, 2 e 3.

---

## Fase 1 — Domínio e motor de decisão, sem LLM

`domain/` e `engine/` completos. Nenhuma chamada de modelo nesta fase.

- `domain/bloom.py` — `BloomLevel`, `BLOOM_ORDER`
- `domain/items.py` — `Item`, `Criterio`, `AntiCriterio`, `ItemFormat`
- `domain/evidence.py` — `Evidencia` e schemas
- `domain/state.py` — `AssessmentState`, `EstadoBloco`, `EstadoCompetencia`, `TurnoRegistro`
- `engine/progression.py` — `decidir_proximo_passo(estado, evidencia) -> Decisao`
- `engine/agreement.py` — a regra de concordância da §5.1
- `engine/config.py` — `MIN_TURNOS_BLOCO`, `TETO_TURNOS_BLOCO`, `TOLERA_ADJACENTE` etc.

`decidir_proximo_passo` é a **fronteira estável** entre a regra v2.0 (concordância) e a v2.1
(erro padrão, 1PL). Projetar a v2.0 já sabendo que a v2.1 troca só a implementação interna.

**Aceite (spec §14):** `pytest` passa; simulação com respondente sintético não produz loop nem
encerramento prematuro; a regra de concordância reproduz as marcações humanas da Fase 0 em pelo
menos **70%** das transcrições.

**Substitui:** `count_messages >= 2` como regra de parada, e o `_get_current_state` que reconstrói
estado varrendo mensagens (`agent_orquestrator.py`).

**Nota:** `TOLERA_ADJACENTE` merece A/B contra os dados anotados. Com 6 níveis, concordância exata
pode ser exigente demais e estourar o teto com frequência.

---

## Fase 2 — Item bank

Autorar itens com critérios para **um bloco piloto**, mais âncoras e aquecimento. Conteúdo curado
offline, versionado, nunca gerado em runtime.

- `bank/loader.py`, `bank/validate.py`
- Mínimo 3 itens por célula, formatos variados (nunca 3 `DIRETA` juntos)
- 3 a 4 itens `ancora`, distribuídos entre blocos
- 1 item `aquecimento` por sessão, sempre o primeiro, nunca pontuado

**Aceite (spec §14):** `bank/validate.py` passa; 3 itens em toda célula do bloco piloto.

**Absorve:** C6 e o `scripts/validate_question_bank.py` atual, que vira `bank/validate.py`.

**Aproveitável do v1 (§17):** as perguntas existentes viram `enunciado` de itens `DIRETA` — cada
célula ainda precisa de dois itens adicionais em outro formato. Os `bloom_levels` com descrição,
`acima` e `abaixo` são reaproveitados integralmente.

**Depende de:** Fase 0, que produz o texto dos `evidencia_gate`.

---

## Fase 3 — Avaliador e golden set

- Migrar `AgentSkillEvaluator` do cliente OpenAI direto para `Agent` do Pydantic AI, com
  `output_type=Evidencia`. O fine-tune continua utilizável, configurado como modelo do agente.
- Injetar `ContextoAvaliacao` — enunciado, resposta, competências, critérios, anti-critérios,
  bloom do item. Sem histórico longo: o avaliador julga um par pergunta/resposta.
- Implementar `validar_evidencia`: trecho citado que não existe na resposta zera o score e
  rebaixa a confiança (P2).
- Anotar 100 casos; suite `pydantic_evals` em `evals/`.

**Aceite (spec §14):** concordância adjacente acima de **0.85**; taxa de trecho alucinado abaixo de
**0.05**; `check_verbosity_bias.py` abaixo de **0.4**.

**Antes de escrever o agente:** instalar a skill oficial do Pydantic AI
(https://pydantic.dev/docs/ai/overview/coding-agent-skills/). A API mudou de forma significativa na
v2 e o código atual usa a antiga. **Não escrever de memória.**

**Absorve:** `message_validator.py`, via `Evidencia.respondeu_a_pergunta`.

**Auditoria pendente (§6.2, mitigação 4):** vale saber de quem eram as respostas que ensinaram o
`bloom-evaluator` o que é "analisar". Se o conjunto era homogêneo em escolaridade ou área, o viés
está nos pesos e nenhum prompt corrige.

---

## Fase 4 — Grafo e persistência

Sem supervisor: a saída é o enunciado cru. O objetivo é provar o circuito, não a conversa.

- Grafo com `pydantic_graph`; apenas `avaliar` e `verbalizar` chamam LLM, o resto é código puro
- `docs/graph.md` gerado por `graph.render()` e verificado no CI — o diagrama vira teste
- Tabelas `assessment_states`, `turns`, `evidence_scores` (§9), append-only
- `SELECT ... FOR UPDATE` na sessão no início do turno
- `lock_version` para lock otimista
- `POST /sessions/{id}/reprocess`

**Aceite (spec §14):** sessão completa ponta a ponta; `/reprocess` reproduz o resultado **sem
chamar LLM**.

`/reprocess` é o teste vivo do P5. Se não existir ou não funcionar, a arquitetura falhou.

`EVIDENCE_SCORES` é a correção definitiva do Pr2: uma linha por critério por turno, com o nível
observado por competência. O C1 é a versão provisória disso dentro do schema atual.

---

## Fase 5 — Supervisor e streaming

- Supervisor apresenta o `enunciado` fixo. Pode acrescentar no máximo meia frase de ligação;
  não reescreve, não resume, não combina perguntas (P6).
- `ponto_forte_anterior` e `lacuna_anterior` chegam ao supervisor — hoje a evidência não chega.
- Streaming; persistência em paralelo ao stream.

**Aceite (spec §14):** 10 sessões manuais sem repetição de estrutura perceptível; tempo até
primeiro token abaixo de **1.5s**.

**Remove:** `question_generator.py` e seus prompts (a fusão de perguntas de referência foi a causa
direta do efeito formulário e viola P6); `helpers/transition_phrases.py` (com `ponto_forte_anterior`
disponível, frase pronta é desnecessária, e lista finita o usuário detecta rápido).

**Não reescrever o `end_prompt`.** A postura avaliativa neutra já está calibrada. As mudanças são
de contexto, não de tom.

De 4 chamadas de LLM por turno para 2.

---

## Fase 6 — Auditoria, relatório e revisão humana

- `GET /admin/sessions/{id}/audit` — turns + evidence_scores completos
- `POST /admin/turns/{id}/human-review` — grava `avaliacao_humana`
- `GET /sessions/{id}/report` — relatório final, só quando encerrada
- Spans OTel (§11) e alertas: confiança baixa acima de 20%, trecho alucinado acima de 5%,
  encerramento por teto acima de 30%, p95 do avaliador acima de 6s

**Por que isso não é refinamento:** a LGPD dá ao titular direito de revisão de decisão automatizada
que afete seus interesses. Na prática, exige explicar um resultado individual **item por item, com
o texto que sustentou cada julgamento**, e ter caminho de revisão humana funcional. O sistema atual
não consegue: o que sobra de uma sessão é um inteiro por turno. Validar o enquadramento com o
jurídico da Koru.

`avaliacao_humana` migra do CSV para `evidence_scores`, onde é consultável.

---

## Fase 7 — Calibração

**Só após ~200 sessões reais.** Sem dados, o modelo é enfeite.

- `calibrate_difficulty.py` — reestima `Item.dificuldade` a partir de dados reais
- `validate_bloom_ladder.py` — taxa média de score por nível deve ser monotônica decrescente
- `check_dif.py` — funcionamento diferencial de item por grupo; item com DIF significativo sai do banco
- Migrar `progression.py` para a regra v2.1: concordância dá lugar a erro padrão abaixo de limiar,
  com modelo 1PL. A interface não muda.

---

## Decisões pendentes

Não devem ser resolvidas com valor default.

| | Decisão | Recomendação da spec | Bloqueia |
|---|---|---|---|
| D1 | Granularidade da competência | blocos para navegação, theta por competência individual | Fase 1 |
| D2 | Orçamento: minutos ou itens | itens — limite de tempo favorece quem digita rápido, variância irrelevante ao construto | Fase 4 |
| D3 | Onde fica o corte de evidência suficiente | não decidir por opinião: rodar a Fase 0 primeiro | Fase 1 |

---

## P7 — Os scripts de verificação

Toda propriedade que a spec afirma tem um script que a verifica. Sem o script, a afirmação não vale.

| Script | O que mede | Critério | Fase | Situação |
|---|---|---|---|---|
| `check_verbosity_bias.py` | correlação entre score e nº de tokens | > 0.4 é alerta vermelho | pré-fase | ✅ existe, sem medição |
| `validate_question_bank.py` | cobertura por célula | 3 itens/célula | pré-fase | ✅ existe, banco reprova |
| `check_agreement_stratified.py` | concordância com humano por estrato | divergência entre estratos indica viés | 3 | ❌ |
| `check_dif.py` | funcionamento diferencial por grupo | item com DIF sai do banco | 7 | ❌ |
| `validate_bloom_ladder.py` | score médio por nível de Bloom | monotônico de `lembrar` a `criar` | 7 | ❌ |
| `calibrate_difficulty.py` | reestima dificuldade | após ~200 sessões | 7 | ❌ |
| `reprocess_session.py` | recomputa sem LLM | reproduz o resultado | 4 | ❌ |

---

## Trilha paralela — corretude do sistema atual

Fora da spec, porque são defeitos e não desenho. Não dependem de fase nenhuma nem de decisão do
time, e valem mesmo que a reconstrução seja abandonada. Podem correr em paralelo à Fase 0.

| | Onde | O quê |
|---|---|---|
| B5 | `services/session.py:244`, `services/evaluation.py:219` | passam `UUID` para `repository.delete()`, que espera a entidade ORM. `DELETE /sessions/{id}` e `DELETE /evaluations/{id}` estão quebrados. |
| B6 | `services/session.py:73`, `:255`, `:265` | `has_owned_resource` chamado antes do teste `if not session`: sessão inexistente vira 500 em vez de 404. |
| B7 | `repository/session.py:52` | `add_message` faz read-modify-write do JSONB sem lock. Duas mensagens simultâneas perdem uma. A Fase 4 resolve de vez com `FOR UPDATE`. |
| B8 | `models/evaluation.py:38` | `EvaluationOutput.iterations: dict`, mas a coluna e o valor são `list`. |
| B10 | `main.py:35` | `Base.metadata.create_all` no lifespan, sem Alembic. As tabelas da §9 não têm por onde entrar. **Bloqueia a Fase 4.** |
| B11 | `skill_evaluator.py:82` | I/O de disco e pandas dentro do caminho async de request, gravando em `artifacts/`, que é efêmero. O C1 já tirou a dependência do dado; falta tirar o I/O. |
| B16 | `config.py:52` | `openai_api_key` existe em `Settings` mas o avaliador lê `os.getenv` direto. |
| B17 | `config.py:133`, `database/db.py:8` | `Settings()` e `create_engine()` rodam em tempo de import: importar `app` exige a configuração inteira e abre um engine. Contornado por `tests/conftest.py`. |
| B18 | `config.py:73`, `:77` | `SecretStr = Field(default=None)`: `SecretStr` não aceita `None`, o default nunca funciona. |
| B9 | 23 ocorrências | `except Exception` genérico devolvendo mensagem cordial (P8). **Fazer por último:** hoje eles escondem os bugs acima. |

B10 é o único item desta trilha que bloqueia uma fase. Os outros são independentes.

---

## Anti-requisitos (§16)

Valem em toda fase. PR que viole qualquer um deve ser rejeitado.

- **Não** gerar perguntas em runtime, nem como fallback. Célula sem item é erro de configuração e
  deve falhar alto.
- **Não** fundir várias perguntas de referência em uma.
- **Não** dar ferramentas ao avaliador. Ele lê e classifica.
- **Não** passar o histórico completo ao avaliador.
- **Não** usar agente orquestrador que decide qual sub-agente chamar. O fluxo é fixo.
- **Não** persistir mensagens como fonte de estado.
- **Não** expor score, nível ou competência ao candidato durante a sessão.
- **Não** implementar IRT antes de ter dados para calibrar.
- **Não** reescrever o `end_prompt` do supervisor.

## Migração do v1 (§17)

Sessões antigas **não são migráveis**. Não existe evidência estruturada nem critério, apenas um
`classificacao` de -1 a 1 derivado de rubricas que eram listas de perguntas. Ficam somente-leitura,
com resultado congelado e marcação explícita de que foram avaliadas pela metodologia v1.
Não tentar recomputar.
