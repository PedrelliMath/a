#!/usr/bin/env python3
import json
import os
import random
import subprocess
import sys

print("="*80)
print("🎯 TESTANDO MODELO COM 100 EXEMPLOS ALEATÓRIOS DO TRAINING DATA")
print("="*80)
print()

# Load .env file
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Get API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("❌ OPENAI_API_KEY não encontrada!")
    sys.exit(1)

MODEL_ID = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"

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
    
    # Preparar payload
    payload = {
        "model": MODEL_ID,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    }
    
    # Chamar o modelo via curl
    try:
        curl_cmd = [
            'curl', '-s',
            'https://api.openai.com/v1/chat/completions',
            '-H', 'Content-Type: application/json',
            '-H', f'Authorization: Bearer {api_key}',
            '-d', json.dumps(payload)
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"❌ Erro curl no exemplo {i}")
            erros += 1
            continue
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            print(f"❌ Erro API no exemplo {i}: {response['error'].get('message', 'Unknown')}")
            erros += 1
            continue
        
        result_str = response['choices'][0]['message']['content']
        result_json = json.loads(result_str)
        result_macro = result_json['adequacao_macro']
        
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
                'system_preview': system_msg[:150]
            })
        
        # Mostrar progresso a cada 10
        if i % 10 == 0:
            acuracia = acertos/(acertos+erros)*100 if (acertos+erros) > 0 else 0
            print(f"Progresso: {i}/{len(amostra)} - Acertos: {acertos}, Erros: {erros} ({acuracia:.1f}%)")
    
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout no exemplo {i}")
        erros += 1
    except Exception as e:
        print(f"❌ Erro no exemplo {i}: {e}")
        erros += 1

print()
print("="*80)
print("📈 RESULTADOS FINAIS")
print("="*80)
total = acertos + erros
print(f"Total testado: {total}")
print(f"✅ Acertos: {acertos}")
print(f"❌ Erros: {erros}")
if total > 0:
    print(f"📊 Acurácia: {acertos/total*100:.2f}%")
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
        print("-"*40)

print()
print("="*80)
