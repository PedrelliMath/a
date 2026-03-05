#!/usr/bin/env python3
import json

# Ler primeiro exemplo do arquivo de treinamento
with open('src/test/valuator/teste_adequacoes.jsonl', 'r') as f:
    exemplo = json.loads(f.readline())

sys_msg = next(m['content'] for m in exemplo['messages'] if m['role'] == 'system')

print("SYSTEM MESSAGE DO ARQUIVO DE TREINAMENTO:")
print("=" * 80)
print(sys_msg)
print("=" * 80)
print()

# Extrair template
idx = sys_msg.find('{"nivel_esperado"')
template = sys_msg[:idx]

print("TEMPLATE (sem dados JSON):")
print(repr(template))
print()

# Verificar palavras-chave
print("CHECKLIST:")
print(f"  ✓ 'justificativa detalhada' presente? {'justificativa detalhada' in sys_msg}")
print(f"  ✓ Termina com 'classificação e justificativa'? {'classificação e justificativa' in sys_msg}")
print(f"  ✓ Menciona 'Além disso'? {'Além disso' in sys_msg}")
