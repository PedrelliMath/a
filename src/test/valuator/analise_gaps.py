import json
import re

with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        system_msg = data['messages'][0]['content']
        assistant_msg = data['messages'][-1]['content']
        result = json.loads(assistant_msg)
        
        if '"nivel_esperado": "lembrar"' in system_msg or '"nivel_esperado": "compreender"' in system_msg or '"nivel_esperado": "aplicar"' in system_msg:
            if result['adequacao_macro'] == '1':
                print('='*80)
                nivel = re.search(r'"nivel_esperado": "(\w+)"', system_msg)
                print(f'NIVEL ESPERADO: {nivel.group(1) if nivel else "N/A"}')
                print(f'CLASSIFICAÇÃO: +1 (acima do esperado)')
                user_msg = data['messages'][1]['content']
                print(f'\nRESPOSTA (primeiros 500 chars):')
                print(user_msg[:500])
                print()
                break
