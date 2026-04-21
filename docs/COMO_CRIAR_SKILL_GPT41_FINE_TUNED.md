# Como criar uma skill usando GPT-4.1 fine-tunado

Este guia explica como qualquer pessoa que copiar esta branch pode criar uma nova skill já usando o mesmo modelo fine-tunado configurado no projeto.

## Modelo fine-tunado usado

Use este ID no campo `agents_config.skill_evaluator.model_name`:

`ft:gpt-4.1-mini-2025-04-14:projeto-koru:bloom-evaluator:DK4dkBG2`

## Onde isso entra no payload

Ao criar a skill (`POST /api/v1/skills/`), inclua a configuração abaixo em `agents_config`:

```json
"agents_config": {
  "supervisor": {
    "model_name": "gpt-4o-mini",
    "temperature": 0.3,
    "max_tokens": 1000
  },
  "question_generator": {
    "model_name": "gpt-4o-mini",
    "temperature": 0.3,
    "max_tokens": 1000
  },
  "question_regenerator": {
    "model_name": "gpt-4o-mini",
    "temperature": 0.3,
    "max_tokens": 1000
  },
  "skill_evaluator": {
    "model_name": "ft:gpt-4.1-mini-2025-04-14:projeto-koru:bloom-evaluator:DK4dkBG2",
    "temperature": 0.0,
    "max_tokens": 1000
  }
}
```

## Passo a passo rápido

1. Suba a API normalmente.
2. Gere/obtenha um token de autenticação (as rotas de skill exigem auth).
3. Faça `POST` em `/api/v1/skills/` com `name`, `description`, `questions` e `agents_config`.
4. Confirme a criação com `GET /api/v1/skills/name/{nome_da_skill}`.

## Exemplo completo com curl, mas mudem apenas a parte de `agents_config.skill_evaluator.model_name` para o ID do modelo fine-tunado fornecido acima, e o name da skill, abaixo ta so um exemplo do que deve ter pra criar toda a competencia.\

Voces podem utilizar o swager tambem.

```bash
curl -X POST "http://localhost:8000/api/v1/skills/" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lideranca GPT41 FT",
    "description": "Skill com avaliacao usando GPT-4.1 fine-tunado",
    "questions": {
      "rubrics": {
        "Autoconhecimento": {
          "lembrar": [
            "Quais comportamentos voce percebe que se repetem em situacoes de pressao?"
          ],
          "compreender": [
            "Como voce descreveria seu estilo de trabalho e seu impacto no time?"
          ],
          "aplicar": [
            "Quais habitos voce cultiva para manter foco e organizacao?"
          ],
          "analisar": [
            "Como voce percebe desalinhamentos entre o que acredita e como age?"
          ],
          "avaliar": [
            "Como voce revisa e adapta seus objetivos pessoais e profissionais?"
          ],
          "criar": [
            "Que estrategias voce usa para construir sua identidade profissional?"
          ]
        }
      },
      "bloom_levels": {
        "lembrar": {"descricao": "...", "acima": "compreender", "abaixo": "lembrar"},
        "compreender": {"descricao": "...", "acima": "aplicar", "abaixo": "lembrar"},
        "aplicar": {"descricao": "...", "acima": "analisar", "abaixo": "compreender"},
        "analisar": {"descricao": "...", "acima": "avaliar", "abaixo": "aplicar"},
        "avaliar": {"descricao": "...", "acima": "criar", "abaixo": "analisar"},
        "criar": {"descricao": "...", "acima": "criar", "abaixo": "avaliar"}
      }
    },
    "agents_config": {
      "supervisor": {"model_name": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 1000},
      "question_generator": {"model_name": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 1000},
      "question_regenerator": {"model_name": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 1000},
      "skill_evaluator": {
        "model_name": "ft:gpt-4.1-mini-2025-04-14:projeto-koru:bloom-evaluator:DK4dkBG2",
        "temperature": 0.0,
        "max_tokens": 1000
      }
    }
  }'
```

## Exemplo via arquivo HTTP do projeto

Voce tambem pode usar o arquivo `src/test/http/skill.http` como base para enviar o `POST` de criacao de skill.

## Como verificar se o modelo fine-tunado foi aplicado

1. Busque a skill criada (`GET /api/v1/skills/name/{nome}`).
2. Confira se no retorno existe:

```json
"agents_config": {
  "skill_evaluator": {
    "model_name": "ft:gpt-4.1-mini-2025-04-14:projeto-koru:bloom-evaluator:DK4dkBG2"
  }
}
```

## Erros comuns

- `401 Unauthorized`: token ausente ou invalido.
- `409 Conflict`: ja existe skill com o mesmo `name`.
- `500` ao avaliar: verificar `OPENAI_API_KEY` no ambiente e formato do `questions`.

## Referencias no codigo

- `src/app/models/skill.py`: exemplo do schema e `model_name` do `skill_evaluator`.
- `src/app/routers/skill.py`: endpoint de criacao `POST /skills/`.
- `src/app/ai/agents/services/agent_orquestrator.py`: leitura de `agents_config.skill_evaluator.model_name` e inicializacao do avaliador.