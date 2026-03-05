#!/bin/bash
# Script para testar o último caso que retornou 0 quando deveria ser +1

echo "================================================================================"
echo "🎯 TESTANDO ÚLTIMA INTERAÇÃO QUE DEU 0 (deveria ser +1)"
echo "================================================================================"
echo

# Carregar variáveis de ambiente
source .env

# Dados exatos da última classificação
DADOS_JSON='{
  "nivel_esperado": "analisar",
  "descricao_nivel_esperado": "Capacidade de dividir informações em partes e entender suas inter-relações. Envolve examinar, categorizar, detectar padrões e identificar causas ou consequências.",
  "pergunta_aferidora": "Uau! Você elaborou um modelo incrível, o \"ecossistema de alinhamento adaptativo\"! Isso nos leva a pensar sobre desafios. Quais padrões você já identificou que dificultavam a colaboração em sua equipe? Como você acredita que a empatia pode superar essas barreiras?",
  "habilidades_macro": {
    "colaboracao": "analisar",
    "empatia": "analisar"
  },
  "nome_grupo": "colaboracao,_empatia",
  "nome_habilidade": "colaboracao",
  "nivel_habilidade": "analisar",
  "registro_id": "1306d00f-1b53-4ee1-b7a0-3c535f17e2c4"
}'

RESPOSTA_USUARIO="Identifiquei três padrões críticos de disfunção colaborativa através de uma solução proprietária que desenvolvi combinando ciência de dados com psicologia organizacional. Primeiro, criei um sistema de monitoramento comportamental usando Python para analisar dados do Slack, Microsoft Teams e Jira. Extraio métricas não convencionais: frequência de interrupções em threads, tempo de resposta entre equipes, padrões linguísticos que indicam desconexão emocional. Desenvolvi algoritmos de NLP (processamento de linguagem natural) com TensorFlow para classificar mensagens em \"colaboração genuína\" vs \"colaboração performática\". Criei um dashboard no Tableau conectado a essas métricas, atualizando em tempo real índices que chamei de \"densidade relacional\" - quantas vezes ideias de colegas são referenciadas e construídas por outros membros.

O segundo padrão foi burnout empático oculto. Implementei um modelo preditivo usando Random Forest em scikit-learn que analisa dados anonimizados de pesquisas de clima, padrões de comunicação extra-horário, volume de mensagens empáticas vs neutras. O algoritmo conseguia prever com 82% de acurácia quando um líder estava entrando em sobrecarga emocional. A solução foi automatizar alertas no sistema e oferecer protocolos estruturados de processamento emocional via app interno que desenvolvi, integrando técnicas de psicologia positiva com gamificação.

O terceiro padrão: desalinhamento de modelos mentais. Desenvolvi uma ferramenta própria de mapeamento usando visão computacional. Durante workshops, cada pessoa desenha processos visualmente, escaneio com OCR, uso OpenCV para detectar diferenças estruturais nos desenhos. Algoritmos de clustering identificam grupos com entendimentos similares/divergentes. A partir disso, criei um \"vocabulário vivo corporativo\" - glossário dinâmico atualizado via ML com base no uso real dos termos na comunicação interna.

Quanto à empatia superar barreiras: desenvolvi o conceito de \"empatia computacional escalável\". Criei um sistema onde conversas difíceis são mediadas por IA que sugere reformulações empáticas em tempo real, baseadas em análise de sentimento e padrões de comunicação não-violenta. O impacto foi transformador: redução de 60% em conflitos, aumento de 45% em índices de segurança psicológica, monitoramento contínuo via paineis automatizados. A inovação foi transformar colaboração e empatia em ciência de dados aplicada, com métricas quantificáveis e sistemas de IA para intervir preventivamente, não reativamente."

# System message (exato como usado no código)
SYSTEM_MESSAGE="Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.
Esses são os dados para classificação: $DADOS_JSON
Considere tambem a resposta do usuario para fazer a classificação e justificativa."

echo "📋 CONTEXTO:"
echo "   Nível esperado: ANALISAR"
echo "   Resposta demonstra: CRIAR (Python, TensorFlow, Random Forest, OpenCV, NLP, etc.)"
echo "   EXPECTATIVA: Deveria retornar +1 (acima do esperado)"
echo
echo "💬 RESPOSTA DO USUÁRIO (preview):"
echo "${RESPOSTA_USUARIO:0:200}..."
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

if adequacao_macro == '1':
    print('   ✅ CORRETO! Modelo classificou como +1 (ACIMA do esperado)')
elif adequacao_macro == '0':
    print('   ❌ ERRO! Modelo classificou como 0 (IGUAL ao esperado)')
    print('   ')
    print('   🔴 PROBLEMA IDENTIFICADO:')
    print('      A resposta claramente demonstra nível CRIAR:')
    print('      - Desenvolveu soluções proprietárias')
    print('      - Criou algoritmos e ferramentas (Python, TensorFlow, Random Forest, OpenCV)')
    print('      - Implementou sistemas inovadores (empatia computacional escalável)')
    print('      - Resultados quantificáveis (60% redução, 45% aumento, 82% acurácia)')
    print('   ')
    print('   ⚠️ O modelo fine-tuned não está reconhecendo corretamente')
    print('      respostas de nível CRIAR quando esperado é ANALISAR')
else:
    print(f'   ⚠️ Modelo retornou: {adequacao_macro}')
" 2>/dev/null)

if [ $? -eq 0 ]; then
  echo "$RESULTADO"
else
  echo "   ⚠️ Não foi possível parsear como JSON"
fi

echo "================================================================================"
