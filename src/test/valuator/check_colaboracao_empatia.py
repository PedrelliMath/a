import json

colaboracao_count = 0
empatia_count = 0
total = 0

with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    for line in f:
        total += 1
        data = json.loads(line)
        system_msg = data['messages'][0]['content']
        
        if 'colaboracao' in system_msg.lower() or 'colaboração' in system_msg.lower():
            colaboracao_count += 1
            
        if 'empatia' in system_msg.lower():
            empatia_count += 1

print(f"Total de exemplos: {total}")
print(f"Exemplos com 'colaboracao': {colaboracao_count} ({colaboracao_count/total*100:.1f}%)")
print(f"Exemplos com 'empatia': {empatia_count} ({empatia_count/total*100:.1f}%)")
print()
print("🔍 Conclusão:")
if colaboracao_count == 0 and empatia_count == 0:
    print("   ❌ NÃO HÁ EXEMPLOS de colaboração/empatia no training data!")
    print("   Isso explica por que o modelo sempre retorna 0 para essas skills.")
else:
    print(f"   ✅ Há exemplos no training data ({colaboracao_count + empatia_count} total)")
