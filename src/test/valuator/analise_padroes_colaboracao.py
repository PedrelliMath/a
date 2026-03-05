import json
import re

print("="*80)
print("EXEMPLOS DE COLABORAÇÃO/EMPATIA NO TRAINING DATA")
print("="*80)
print()

# Procurar exemplos de diferentes classificações
exemplos = {
    '-1': [],
    '0': [],
    '1': []
}

with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        system_msg = data['messages'][0]['content']
        user_msg = data['messages'][1]['content']
        assistant_msg = data['messages'][-1]['content']
        
        # Só pegar exemplos de colaboração/empatia
        if 'colaboracao' not in system_msg.lower() and 'empatia' not in system_msg.lower():
            continue
            
        result = json.loads(assistant_msg)
        classificacao = result['adequacao_macro']
        
        # Extrair nivel_esperado
        nivel_match = re.search(r'"nivel_esperado": "(\w+)"', system_msg)
        nivel_esperado = nivel_match.group(1) if nivel_match else "N/A"
        
        if classificacao in exemplos and len(exemplos[classificacao]) < 2:
            exemplos[classificacao].append({
                'nivel_esperado': nivel_esperado,
                'resposta': user_msg[:600],
                'system': system_msg
            })

# Mostrar exemplos
for classificacao in ['-1', '0', '1']:
    print(f"\n{'='*80}")
    print(f"CLASSIFICAÇÃO: {classificacao}")
    print(f"{'='*80}")
    
    for i, ex in enumerate(exemplos[classificacao], 1):
        print(f"\nEXEMPLO {i}:")
        print(f"Nível esperado: {ex['nivel_esperado']}")
        print(f"\nResposta (primeiros 600 chars):")
        print(ex['resposta'])
        print("-"*80)
