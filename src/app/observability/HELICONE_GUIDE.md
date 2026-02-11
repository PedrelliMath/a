# 📊 Guia de Observabilidade com Helicone

## O que é o Helicone?

O **Helicone** é uma plataforma de observabilidade para LLMs (Large Language Models) que permite:

- 📈 **Monitorar** todas as chamadas para modelos de IA (GPT-4, GPT-3.5, etc.)
- 💰 **Rastrear custos** de tokens e uso de API
- ⚡ **Medir performance** (latência, throughput)
- 🔍 **Debugar** prompts e respostas
- 📊 **Analisar** padrões de uso

## Como está implementado neste projeto?

### 1. Arquitetura

```
┌─────────────────┐
│   Agentes IA    │
│  (Supervisor,   │
│  Evaluator,     │
│  Generator)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  @track_helicone│  ← Decorator que captura métricas
│    Decorator    │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌──────────────────┐
│  Helicone API   │  │  PostgreSQL      │
│  (Opcional)     │  │  helicone_metrics│
└─────────────────┘  └──────────────────┘
```

### 2. Dados Capturados

Cada chamada de IA captura:

- **Identificação**: `request_id`, `session_id`, `user_id`
- **Agente**: Tipo (supervisor, evaluator, generator, validator)
- **Modelo**: Nome do modelo LLM usado
- **Performance**: Latência em milissegundos
- **Tokens**: Prompt tokens, completion tokens, total
- **Custo**: Estimativa em USD
- **Timestamp**: Data/hora da chamada

### 3. Tabela no PostgreSQL

```sql
CREATE TABLE helicone_metrics (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE,
    request_id VARCHAR(255),
    session_id VARCHAR(255),
    user_id VARCHAR(255),
    agent_type VARCHAR(50),
    model VARCHAR(100),
    latency_ms FLOAT,
    tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost FLOAT,
    -- Campos para guardrails (DeepEval) - futuro
    overall_safety_score FLOAT,
    violations_count INTEGER,
    is_safe BOOLEAN,
    bias_score FLOAT,
    toxicity_score FLOAT,
    ...
);
```

## Como habilitar?

### Opção 1: Apenas logs locais (PostgreSQL)

Adicione no seu `.env`:

```bash
# Helicone - Observabilidade
HELICONE_ENABLED=true
# Deixe HELICONE_API_KEY vazio para apenas logs locais
```

**Vantagens:**
- ✅ Gratuito
- ✅ Dados ficam no seu banco
- ✅ Privacidade total
- ❌ Sem dashboard visual

### Opção 2: Helicone completo (com dashboard)

1. **Crie uma conta gratuita**: https://www.helicone.ai/
2. **Obtenha sua API Key**: Dashboard → Settings → API Keys
3. **Configure no `.env`**:

```bash
# Helicone - Observabilidade
HELICONE_ENABLED=true
HELICONE_API_KEY=sk-helicone-xxxxxxxx
HELICONE_BASE_URL=https://oai.helicone.ai/v1
```

**Vantagens:**
- ✅ Dashboard visual bonito
- ✅ Gráficos e análises
- ✅ Alertas e notificações
- ✅ Comparação de modelos
- ✅ Logs locais + cloud

## Como usar?

### 1. Habilitar no .env

```bash
HELICONE_ENABLED=true
```

### 2. Reiniciar a API

```bash
docker-compose restart chatbot-api
```

### 3. Usar a aplicação normalmente

Crie chats, envie mensagens. As métricas serão capturadas automaticamente!

### 4. Visualizar métricas locais

Execute o script de visualização:

```bash
python view_helicone_logs.py
```

Ou consulte diretamente no PostgreSQL:

```sql
-- Total de chamadas por agente
SELECT agent_type, COUNT(*), AVG(latency_ms), SUM(tokens)
FROM helicone_metrics
GROUP BY agent_type;

-- Últimas 10 métricas
SELECT timestamp, agent_type, model, latency_ms, tokens, cost
FROM helicone_metrics
ORDER BY timestamp DESC
LIMIT 10;

-- Custo total por sessão
SELECT session_id, SUM(cost) as total_cost, SUM(tokens) as total_tokens
FROM helicone_metrics
GROUP BY session_id;
```

### 5. Acessar o Dashboard Helicone (se configurado)

Acesse: https://www.helicone.ai/dashboard

## Agentes rastreados

Os seguintes agentes têm o decorator `@track_helicone`:

1. **Supervisor** (`supervisor`)
   - Coordena o fluxo de conversação
   - Decide próximos passos

2. **Message Validator** (`message_validator`)
   - Valida mensagens do usuário
   - Detecta off-topic

3. **Skill Evaluator** (`skill_evaluator`)
   - Avalia respostas do usuário
   - Calcula níveis Bloom

4. **Question Generator** (`question_generator`)
   - Gera novas perguntas
   - Adapta dificuldade

## Exemplo de métricas capturadas

```
[AGENTE] question_generator:
   - Chamadas: 5
   - Latencia media: 1234.56ms
   - Total de tokens: 2500
   - Custo total: $0.0125

[AGENTE] skill_evaluator:
   - Chamadas: 5
   - Latencia media: 987.32ms
   - Total de tokens: 1800
   - Custo total: $0.0090
```

## Desabilitar Helicone

Se não quiser usar, simplesmente:

```bash
HELICONE_ENABLED=false
```

As métricas não serão mais capturadas.

## Troubleshooting

### Nenhuma métrica está sendo capturada

1. Verifique se `HELICONE_ENABLED=true` no `.env`
2. Reinicie o container: `docker-compose restart chatbot-api`
3. Verifique os logs: `docker logs chatbot_api | grep -i helicone`
4. Crie um chat e envie mensagens para gerar métricas

### Erro ao salvar métricas

- As métricas são salvas de forma **não-bloqueante**
- Se houver erro, não interrompe o fluxo da aplicação
- Verifique os logs para detalhes

### Tabela não existe

Execute as migrations:

```bash
docker exec -it chatbot_api alembic upgrade head
```

## Custos

### Helicone (plataforma)
- **Free Tier**: 100k requests/mês grátis
- **Pro**: $20/mês para 1M requests
- Mais info: https://www.helicone.ai/pricing

### OpenAI (tokens)
- Os custos de tokens são da OpenAI, não do Helicone
- Helicone apenas monitora e exibe os custos
- GPT-4o-mini: ~$0.15 / 1M tokens input, ~$0.60 / 1M tokens output

## Recursos adicionais

- 📚 Documentação oficial: https://docs.helicone.ai/
- 🎥 Tutoriais: https://www.helicone.ai/blog
- 💬 Discord: https://discord.gg/helicone
