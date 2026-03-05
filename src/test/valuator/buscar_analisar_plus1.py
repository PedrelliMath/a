import json
import re

print("Buscando exemplos onde esperava ANALISAR e retornou +1...")
print()

count = 0
with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        system_msg = data['messages'][0]['content']
        assistant_msg = data['messages'][-1]['content']
        result = json.loads(assistant_msg)
        
        if '"nivel_esperado": "analisar"' in system_msg:
            if result['adequacao_macro'] == '1':
                count += 1
                print('='*80)
                print(f'EXEMPLO {count}: NIVEL ESPERADO = analisar, CLASSIFICAÇÃO = +1 (acima)')
                user_msg = data['messages'][1]['content']
                print(f'\nRESPOSTA (primeiros 600 chars):')
                print(user_msg[:600])
                print()
                
                if count >= 3:
                    break

if count == 0:
    print("❌ NÃO FORAM ENCONTRADOS exemplos onde esperava ANALISAR e retornou +1!")
    print("Isso explica o problema: O modelo nunca foi treinado para classificar como +1 quando esperado é ANALISAR")
