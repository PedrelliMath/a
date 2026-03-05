#!/bin/bash
# Script para testar o skill evaluator fine-tuned

echo "================================================================================"
echo "🎯 TESTANDO SKILL EVALUATOR FINE-TUNED"
echo "================================================================================"
echo

# Carregar variáveis de ambiente
source .env

# Dados de classificação
DADOS_JSON='{
  "nivel_esperado": "lembrar",
  "descricao_nivel_esperado": "Capacidade de recordar fatos, conceitos e informações básicas aprendidas anteriormente. Envolve identificar, listar, nomear ou reconhecer informações sem a necessidade de interpretação ou aplicação.",
  "pergunta_aferidora": "Como você percebe desalinhamentos entre o que acredita e como age?",
  "habilidades_macro": {
    "autoconhecimento": "lembrar"
  },
  "nome_grupo": "autoconhecimento",
  "nome_habilidade": "autoconhecimento",
  "nivel_habilidade": "lembrar",
  "registro_id": "8520e12b-2e05-4e21-bf93-fca1f19e4c00"
}'

RESPOSTA_USUARIO="percebi que muitas vezes digo que valorizo o equilibrio entre vida pessoal e trabalho, mas quando olho para minha rotina, percebo que frequentemente fico ate mais tarde no escritorio, mesmo quando nao e necessario. outro exemplo e quando falo sobre a importancia de delegar tarefas, mas acabo assumindo muitas responsabilidades sozinho. tambem noto que defendo a comunicacao aberta, mas as vezes hesito em compartilhar feedbacks dificeis com minha equipe. reconheco esses desalinhamentos quando paro para refletir sobre meu dia a dia."

# System message
SYSTEM_MESSAGE="Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.

Esses são os dados para classificação: $DADOS_JSON

Considere tambem a resposta do usuario para fazer a classificação e justificativa."

echo "📋 DADOS DE CLASSIFICAÇÃO:"
echo "$DADOS_JSON" | python3 -m json.tool
echo
echo "💬 RESPOSTA DO USUÁRIO:"
echo "$RESPOSTA_USUARIO"
echo
echo "🤖 Chamando modelo fine-tuned..."
echo

# Fazer request para OpenAI
RESPONSE=$(curl -s https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d "{
    \"model\": \"ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5\",
    \"temperature\": 0.0,
    \"messages\": [
      {
        \"role\": \"system\",
        \"content\": $(echo "$SYSTEM_MESSAGE" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
      },
      {
        \"role\": \"user\",
        \"content\": $(echo "$RESPOSTA_USUARIO" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
      }
    ]
  }")

echo "================================================================================"
echo "🔍 RESPOSTA BRUTA DO MODELO FINE-TUNED:"
echo "================================================================================"
echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['choices'][0]['message']['content'])"
echo "================================================================================"
echo

# Tentar parsear resultado
echo "✅ PARSEANDO RESULTADO:"
RESULTADO=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); resultado=json.loads(data['choices'][0]['message']['content']); print(f\"   Adequação Macro: {resultado.get('adequacao_macro', 'N/A')}\"); print(f\"   Adequação Habilidades: {resultado.get('adequacao_habilidades', 'N/A')}\"); classificacao=int(resultado.get('adequacao_macro', '0')); print(); print('   📈 Nível ACIMA do esperado' if classificacao == 1 else '   📊 Nível IGUAL ao esperado' if classificacao == 0 else '   📉 Nível ABAIXO do esperado')" 2>/dev/null)

if [ $? -eq 0 ]; then
  echo "$RESULTADO"
else
  echo "   ⚠️ Não foi possível parsear como JSON"
fi
