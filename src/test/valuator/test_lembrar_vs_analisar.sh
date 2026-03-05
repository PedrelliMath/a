#!/bin/bash
# Script para testar resposta LEMBRAR quando esperado é ANALISAR (deveria dar -1)

echo "================================================================================"
echo "🎯 TESTANDO RESPOSTA NÍVEL LEMBRAR (esperado: ANALISAR)"
echo "================================================================================"
echo

# Carregar variáveis de ambiente
source .env

# Dados exatos - esperando ANALISAR
DADOS_JSON='{
  "nivel_esperado": "analisar",
  "descricao_nivel_esperado": "Capacidade de dividir informações em partes e entender suas inter-relações. Envolve examinar, categorizar, detectar padrões e identificar causas ou consequências.",
  "pergunta_aferidora": "Quais padrões você já identificou que dificultavam a colaboração nas equipes?",
  "habilidades_macro": {
    "colaboracao": "analisar",
    "empatia": "analisar"
  },
  "nome_grupo": "colaboracao,_empatia",
  "nome_habilidade": "colaboracao",
  "nivel_habilidade": "analisar",
  "registro_id": "test-lembrar"
}'

# Resposta de nível LEMBRAR (apenas reconhece/lista, sem análise profunda)
RESPOSTA_USUARIO="percebi que alguns problemas de colaboracao eram falhas de comunicacao e reunioes que duravam muito tempo. tambem notei que as pessoas nem sempre respondiam mensagens rapidamente. outro ponto era que nem todos participavam das discussoes. lembro de casos onde informacoes importantes nao eram compartilhadas com toda a equipe. as vezes havia conflitos por mal-entendidos."

# System message
SYSTEM_MESSAGE="Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.
Esses são os dados para classificação: $DADOS_JSON
Considere tambem a resposta do usuario para fazer a classificação e justificativa."

echo "📋 CONTEXTO:"
echo "   Nível esperado: ANALISAR"
echo "   Resposta demonstra: LEMBRAR (apenas lista problemas, sem análise de padrões)"
echo "   EXPECTATIVA: Deveria retornar -1 (abaixo do esperado)"
echo
echo "💬 RESPOSTA DO USUÁRIO:"
echo "$RESPOSTA_USUARIO"
echo
echo "🤖 Chamando modelo fine-tuned (temperature=0.0)..."
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
RESULTADO_RAW=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['choices'][0]['message']['content'])")
echo "$RESULTADO_RAW"
echo "================================================================================"
echo

# Tentar parsear resultado
echo "✅ PARSEANDO RESULTADO:"
RESULTADO=$(echo "$RESULTADO_RAW" | python3 -c "
import sys, json
resultado = json.loads(sys.stdin.read())
adequacao_macro = resultado.get('adequacao_macro', 'N/A')
adequacao_hab = resultado.get('adequacao_habilidades', 'N/A')
print(f'   Adequação Macro: {adequacao_macro}')
print(f'   Adequação Habilidades: {adequacao_hab}')
print()

if adequacao_macro == '-1':
    print('   ✅ CORRETO! Modelo classificou como -1 (ABAIXO do esperado)')
    print('   O modelo consegue detectar respostas de nível baixo (LEMBRAR) corretamente')
elif adequacao_macro == '0':
    print('   ❌ ERRO! Modelo classificou como 0 (IGUAL ao esperado)')
    print('   A resposta só lista problemas, não analisa padrões ou causas')
elif adequacao_macro == '1':
    print('   ❌ ERRO GRAVE! Modelo classificou como +1 (ACIMA do esperado)')
    print('   A resposta é claramente nível LEMBRAR, não CRIAR')
else:
    print(f'   ⚠️ Modelo retornou: {adequacao_macro}')
" 2>/dev/null)

if [ $? -eq 0 ]; then
  echo "$RESULTADO"
else
  echo "   ⚠️ Não foi possível parsear como JSON"
fi

echo "================================================================================"
