#!/usr/bin/env python3
import json
import os
import random
from openai import OpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

MODEL_ID = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"

print("="*80)
print("🎯 TESTANDO MODELO COM 100 EXEMPLOS ALEATÓRIOS DO TRAINING DATA")
print("="*80)
print()

# Ler todos os exemplos
exemplos = []
with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    for line in f:
        exemplos.append(json.loads(line))

# Selecionar 100 aleatórios
random.seed(42)  # Para reprodutibilidade
amostra = random.sample(exemplos, min(100, len(exemplos)))

print(f"📊 Total de exemplos no dataset: {len(exemplos)}")
print(f"🎲 Testando com: {len(amostra)} exemplos aleatórios")
print(f"🌡️  Temperature: 0.0")
print()

acertos = 0
erros = 0
detalhes_erros = []

for i, exemplo in enumerate(amostra, 1):
    system_msg = exemplo['messages'][0]['content']
    user_msg = exemplo['messages'][1]['content']
    expected = json.loads(exemplo['messages'][2]['content'])
    expected_macro = expected['adequacao_macro']
    
    # Chamar o modelo
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ]
        )
        
        result_str = response.choices[0].message.content
        result = json.loads(result_str)
        result_macro = result['adequacao_macro']
        
        if result_macro == expected_macro:
            acertos += 1
            status = "✅"
        else:
            erros += 1
            status = "❌"
            detalhes_erros.append({
                'exemplo': i,
                'esperado': expected_macro,
                'retornado': result_macro,
                'system_preview': system_msg[:200]
            })
        
        # Mostrar progresso a cada 10
        if i % 10 == 0:
            print(f"Progresso: {i}/{len(amostra)} - Acertos: {acertos}, Erros: {erros} ({acertos/(acertos+erros)*100:.1f}%)")
    
    except Exception as e:
        print(f"❌ Erro no exemplo {i}: {e}")
        erros += 1

print()
print("="*80)
print("📈 RESULTADOS FINAIS")
print("="*80)
print(f"Total testado: {acertos + erros}")
print(f"✅ Acertos: {acertos}")
print(f"❌ Erros: {erros}")
print(f"📊 Acurácia: {acertos/(acertos+erros)*100:.2f}%")
print()

if detalhes_erros:
    print("="*80)
    print(f"🔍 DETALHES DOS ERROS (primeiros 10):")
    print("="*80)
    for erro in detalhes_erros[:10]:
        print(f"\nExemplo #{erro['exemplo']}:")
        print(f"  Esperado: {erro['esperado']}")
        print(f"  Retornado: {erro['retornado']}")
        print(f"  Context: {erro['system_preview']}...")
        print("-"*80)

print()
print("="*80)
