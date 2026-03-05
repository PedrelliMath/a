#!/bin/bash
# Testa a mesma resposta com diferentes níveis esperados

echo "================================================================================"
echo "🔬 TESTE COMPARATIVO: MESMA RESPOSTA, DIFERENTES NÍVEIS ESPERADOS"
echo "================================================================================"
echo

source .env

# Resposta adequada para nível "lembrar"
RESPOSTA_USUARIO="percebi que muitas vezes digo que valorizo o equilibrio entre vida pessoal e trabalho, mas quando olho para minha rotina, percebo que frequentemente fico ate mais tarde no escritorio, mesmo quando nao e necessario. outro exemplo e quando falo sobre a importancia de delegar tarefas, mas acabo assumindo muitas responsabilidades sozinho. tambem noto que defendo a comunicacao aberta, mas as vezes hesito em compartilhar feedbacks dificeis com minha equipe. reconheco esses desalinhamentos quando paro para refletir sobre meu dia a dia."

# Função para testar
testar_nivel() {
    local NIVEL=$1
    local DESCRICAO=$2
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 TESTANDO COM NÍVEL ESPERADO: $NIVEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    DADOS_JSON="{
  \"nivel_esperado\": \"$NIVEL\",
  \"descricao_nivel_esperado\": \"$DESCRICAO\",
  \"pergunta_aferidora\": \"Como você percebe desalinhamentos entre o que acredita e como age?\",
  \"habilidades_macro\": {
    \"autoconhecimento\": \"$NIVEL\"
  },
  \"nome_grupo\": \"autoconhecimento\",
  \"nome_habilidade\": \"autoconhecimento\",
  \"nivel_habilidade\": \"$NIVEL\",
  \"registro_id\": \"test-001\"
}"

    SYSTEM_MESSAGE="Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.

Esses são os dados para classificação: $DADOS_JSON

Considere tambem a resposta do usuario para fazer a classificação e justificativa."

    echo "🔍 Descrição do nível: $DESCRICAO"
    echo
    
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
    
    RESULTADO=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['choices'][0]['message']['content'])")
    
    echo "📊 RESULTADO:"
    echo "$RESULTADO" | python3 -m json.tool
    
    ADEQUACAO=$(echo "$RESULTADO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('adequacao_macro', 'N/A'))")
    
    echo
    if [ "$ADEQUACAO" = "1" ]; then
        echo "   📈 Classificação: +1 (ACIMA do esperado)"
    elif [ "$ADEQUACAO" = "0" ]; then
        echo "   📊 Classificação: 0 (IGUAL ao esperado)"
    elif [ "$ADEQUACAO" = "-1" ]; then
        echo "   📉 Classificação: -1 (ABAIXO do esperado)"
    fi
    echo
}

echo "💬 RESPOSTA DO USUÁRIO (usada em todos os testes):"
echo "$RESPOSTA_USUARIO"
echo
echo

# Testar com diferentes níveis
testar_nivel "lembrar" "Capacidade de recordar fatos, conceitos e informações básicas aprendidas anteriormente. Envolve identificar, listar, nomear ou reconhecer informações sem a necessidade de interpretação ou aplicação."

testar_nivel "compreender" "Capacidade de entender o significado de informações, interpretar exemplos e parafrasear conceitos. Envolve explicar, descrever e comparar informações de maneira organizada."

testar_nivel "aplicar" "Capacidade de usar conhecimento em situações concretas. Envolve executar, implementar e utilizar metodologias ou ferramentas em contextos práticos do dia a dia."

testar_nivel "analisar" "Capacidade de dividir informações em partes e entender suas inter-relações. Envolve examinar, categorizar, detectar padrões e identificar causas ou consequências."

testar_nivel "avaliar" "Capacidade de fazer julgamentos baseados em critérios. Envolve criticar, recomendar, justificar decisões e comparar alternativas com base em evidências."

testar_nivel "criar" "Capacidade de produzir algo novo e original. Envolve projetar, desenvolver, propor soluções inovadoras e criar produtos ou ideias inéditas."

echo
echo "================================================================================"
echo "📋 RESUMO ESPERADO:"
echo "================================================================================"
echo
echo "A resposta demonstra reconhecimento/identificação de desalinhamentos (nível LEMBRAR)"
echo
echo "Resultados esperados:"
echo "   • lembrar: 0 (resposta está no nível esperado)"
echo "   • compreender: -1 (resposta está abaixo, não explica causas)"
echo "   • aplicar: -1 (resposta não aplica metodologias)"
echo "   • analisar: -1 (resposta não analisa profundamente relações)"
echo "   • avaliar: -1 (resposta não compara alternativas)"
echo "   • criar: -1 (resposta não propõe soluções inovadoras)"
echo
echo "================================================================================"
