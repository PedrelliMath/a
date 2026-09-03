# Koru — contexto do projeto

Motor de assessment adaptativo conversacional. Estima proficiência de candidatos em competências, medidas na taxonomia de Bloom.

**O projeto está em reconstrução (v2).** A especificação completa está em `docs/koru-v2-spec.md`. Leia antes de qualquer mudança estrutural.

## Stack

- Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL, Keycloak, PDM
- **Pydantic AI v2**, Pydantic Graph, Pydantic Evals
- Frontend React/TypeScript com Bun

## Antes de escrever código de agente

A API do Pydantic AI mudou de forma significativa na v2 e o código atual em `src/app/ai/` usa a API antiga. **Não escreva de memória.** Instale a skill oficial:

https://pydantic.dev/docs/ai/overview/coding-agent-skills/

Referências:
- `GraphBuilder`, `g.step`, `g.node`, `g.edge_from().to()` → https://pydantic.dev/docs/ai/graph/builder/
- `BaseNode`, `GraphRunContext`, `End` → https://pydantic.dev/docs/ai/graph/graph/
- `Agent`, `output_type`, `deps_type` → https://pydantic.dev/docs/ai/core-concepts/agent/
- `Dataset`, `Case`, evaluators → https://pydantic.dev/docs/ai/evals/getting-started/quick-start/

Confirme identificadores de modelo em https://pydantic.dev/docs/ai/models/overview/. Todo modelo vem de config, nunca hardcoded.

## Princípios de arquitetura

Não negociáveis. Rejeite mudanças que violem qualquer um.

1. **O LLM observa, o código decide.** Nenhum agente retorna nível final, progressão ou decisão de encerramento. Agentes retornam evidência estruturada; a progressão é função pura dessa evidência.
2. **Toda afirmação avaliativa cita a fonte.** Todo score carrega um trecho literal da resposta, verificado em código contra o texto original.
3. **O estado é explícito e persistido.** `AssessmentState` é a única fonte de verdade. Proibido derivar estado varrendo mensagens.
4. **A rubrica nunca chega ao gerador de perguntas.** O candidato não recebe o instrumento de medição parafraseado.
5. **Reprocessamento sem LLM.** O resultado deve ser recomputável a partir das evidências persistidas, em código puro.
6. **Mesmo estímulo na mesma posição.** Candidatos na mesma célula recebem o mesmo item, com texto fixo.
7. **Nada é medido sem ser medível.** Toda afirmação de qualidade ou justiça tem um script em `scripts/` que a verifica.
8. **Falha explícita.** Sem `except Exception` genérico devolvendo mensagem cordial.

## Contexto de domínio

- **Bloom**: lembrar, compreender, aplicar, analisar, avaliar, criar. Nessa ordem.
- **Bloco**: agrupamento de competências usado para navegação. Hoje são 4 chaves contendo 10 competências separadas por vírgula.
- **Competência**: unidade individual de medição, dentro de um bloco.
- **Célula**: par bloco × nível de Bloom. Cada célula precisa de no mínimo 3 itens.
- **Item**: pergunta fixa, versionada, com critérios de avaliação anexados.
- **Âncora**: item que todo candidato vê, independente do caminho adaptativo.

## Cuidados específicos deste código

- `src/app/ai/agents/services/agent_orquestrator.py` tem `_generate_supervisor_response` **definido duas vezes**. A primeira é copy-paste quebrado do `_handle_skip`. Python usa a segunda.
- `src/app/ai/agents/helpers/state_initializer.py` importa módulos inexistentes (`app.db.models`). Dá ImportError. É resto de arquitetura anterior.
- `skill.questions.rubrics` **não contém rubricas**, apenas listas de perguntas por nível. Não presuma que existe critério de avaliação em lugar nenhum do sistema atual.
- O avaliador usa um modelo fine-tuned via cliente OpenAI direto, fora do Pydantic AI. Migrar com cuidado.
- O `end_prompt` do supervisor em `ai/agents/prompts/supervisor.py` já tem a postura avaliativa neutra bem calibrada. **Não reescrever o tom.**

## Este é um sistema que decide sobre pessoas

Resultados afetam candidatos em processos de RH. Isso muda o padrão de qualidade:

- Nunca exponha score, nível estimado ou competência ao candidato durante a sessão.
- Todo resultado precisa ser explicável item por item, com o texto que sustentou cada julgamento.
- Registro verbal, vocabulário, extensão e correção gramatical **nunca** são critérios de avaliação. Modelos confundem sofisticação verbal com complexidade cognitiva, e isso penaliza escolaridade formal e registro regional.
- Ao mexer no avaliador ou na rubrica, rode `scripts/check_verbosity_bias.py` antes de abrir PR.

## Convenções

- Código, nomes de variável e docstrings em português, seguindo o padrão existente.
- Logs estruturados via `app.logger.get_log`.
- Testes em `tests/`, evals em `evals/`. Mudança em prompt ou rubrica exige rodar a suite de evals.
- `docs/graph.md` é gerado por `graph.render()` e verificado no CI. Se o grafo mudar, regenere.
