#!/bin/bash

# Script para testar o fluxo completo da API
BASE_URL="http://localhost:8000/api/v1"

echo "=== 1. Criando Skill ==="
SKILL_RESPONSE=$(curl -s -X POST "$BASE_URL/skills/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Atendimento ao Cliente",
    "description": "Skill para avaliar atendimento",
    "questions": {
      "q1": "Como você lida com clientes insatisfeitos?",
      "q2": "Descreva técnicas de comunicação eficaz"
    }
  }')

echo "$SKILL_RESPONSE" | jq '.'
SKILL_ID=$(echo "$SKILL_RESPONSE" | jq -r '.id')
echo "Skill ID: $SKILL_ID"

echo -e "\n=== 2. Criando Session ==="
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/sessions/" \
  -H "Content-Type: application/json" \
  -d "{\"skill_id\": \"$SKILL_ID\"}")

echo "$SESSION_RESPONSE" | jq '.'
SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.id')
echo "Session ID: $SESSION_ID"

echo -e "\n=== 3. Enviando primeira mensagem (início do chat) ==="
MSG1=$(curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"text": "Olá! Estou pronto para a avaliação."}')

echo "$MSG1" | jq '.'

echo -e "\n=== 4. Enviando resposta à primeira pergunta ==="
MSG2=$(curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"text": "Eu escuto atentamente o cliente, reconheço suas preocupações e busco soluções imediatas. Mantenho a calma e ofereço alternativas."}')

echo "$MSG2" | jq '.'

echo -e "\n=== 5. Enviando resposta àsegunda pergunta ==="
MSG3=$(curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"text": "Comunicação clara, objetiva e empática. Uso linguagem simples, confirmo entendimento do cliente e faço perguntas abertas."}')

echo "$MSG3" | jq '.'

echo -e "\n=== 6. Consultando session com histórico ==="
curl -s -X GET "$BASE_URL/sessions/$SESSION_ID" | jq '.'

echo -e "\n=== 7. Listando todas as sessions ==="
curl -s -X GET "$BASE_URL/sessions/" | jq '.'

echo -e "\n✅ Fluxo completo executado!"
echo "Session ID para referência: $SESSION_ID"
