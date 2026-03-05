#!/bin/bash
# Testar resposta nivel CRIAR quando esperado é ANALISAR

source .env

DADOS_JSON='{
  "nivel_esperado": "analisar",
  "descricao_nivel_esperado": "Capacidade de dividir informações em partes e entender suas inter-relações. Envolve examinar, categorizar, detectar padrões e identificar causas ou consequências.",
  "pergunta_aferidora": "quais padroes voce ja identificou que dificultavam a colaboracao nas equipes?",
  "habilidades_macro": {
    "colaboracao": "analisar",
    "empatia": "analisar"
  },
  "nome_grupo": "grupo_01",
  "nome_habilidade": "colaboracao",
  "nivel_habilidade": "analisar",
  "registro_id": "test123"
}'

RESPOSTA_USUARIO="identifiquei tres padroes que chamo de armadilhas invisiveis da colaboracao, que so detectei ao criar um sistema proprio de analise comportamental. o primeiro padrao e o que denominei colaboracao performatica: pessoas que participam de reunioes e parecem engajadas, mas seus comportamentos nao-verbais - frequencia de interrupcoes, tempo ate responder mensagens de outros times, padroes de linguagem nas respostas - revelavam desconexao profunda. desenvolvi metricas qualitativas para isso, mapeando nao so participacao, mas densidade relacional - quantas ideias de um colega cada pessoa referencia e constroi sobre. o segundo padrao foi o burnout empatico oculto: lideres que genuinamente se importam, mas cuja empatia vira sobrecarga emocional. identifiquei que isso acontecia quando a pessoa nao tinha estruturas para processar as emocoes do time, entao absorvia tudo internamente. criei um protocolo que chamei de empatia estruturada - sessoes quinzenais onde lideres mapeiam suas reacoes emocionais as situacoes do time, identificando quando estao confundindo empatia com responsabilidade emocional total. o terceiro foi o desalinhamento de modelos mentais: times que usavam as mesmas palavras mas tinham entendimentos radicalmente diferentes. desenvolvi workshops onde pediamos para cada pessoa desenhar visualmente como via um processo ou conceito, e as divergencias eram chocantes - alinhamento significava coisas completamente diferentes. propus entao um framework de vocabulario vivo, onde termos-chave sao continuamente redefinidos coletivamente com exemplos concretos. para escalar esse diagnostico, criei uma ferramenta de analise semantica em conversas do slack que detecta esses padroes automaticamente - palavras que indicam colaboracao performatica vs. real, sinais linguisticos de burnout empatico, divergencias semanticas. isso permitiu intervencoes preventivas, nao reativas. o impacto foi transformador: reduzimos conflitos em 60% nao eliminando divergencias, mas tornando-as explicitas e produtivas. a inovacao foi tratar colaboracao nao como valor aspiracional, mas como sistema diagnosticavel e otimizavel com metricas proprias que criei especificamente para capturar nuances humanas."

SYSTEM_MESSAGE="Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.
Esses são os dados para classificação: $DADOS_JSON
Considere tambem a resposta do usuario para fazer a classificação e justificativa."

echo "🎯 TESTANDO RESPOSTA NIVEL CRIAR (esperado: ANALISAR)"
echo "======================================================================"
echo ""
echo "📋 Nível esperado: ANALISAR"
echo "💬 Resposta demonstra: CRIAR (frameworks próprios, métricas inovadoras)"
echo ""
echo "🤖 Chamando modelo fine-tuned (temperature=0.0)..."
echo ""

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

echo "🔍 RESPOSTA DO MODELO:"
echo "$RESULTADO"
echo ""

ADEQUACAO=$(echo "$RESULTADO" | python3 -c "import sys, json; r=json.load(sys.stdin); print(r.get('adequacao_macro', 'N/A'))")

echo "======================================================================"
if [ "$ADEQUACAO" = "1" ]; then
  echo "✅ CORRETO! Modelo classificou como +1 (ACIMA do esperado)"
elif [ "$ADEQUACAO" = "0" ]; then
  echo "❌ ERRO! Modelo classificou como 0 (IGUAL) quando deveria ser +1"
else
  echo "⚠️ Modelo classificou como: $ADEQUACAO"
fi
echo "======================================================================"
