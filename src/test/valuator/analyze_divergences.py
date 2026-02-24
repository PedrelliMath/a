"""
Análise de divergências entre adequacao_macro e adequacao_habilidades
"""
import json
import os
from collections import defaultdict
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"
OPENAI_BASE_URL = "https://api.openai.com/v1"


def carregar_todos_exemplos(arquivo):
    """Carrega todos os exemplos do arquivo JSONL"""
    exemplos = []
    with open(arquivo, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            data = json.loads(line)
            assistant_msg = next(m for m in data['messages'] if m['role'] == 'assistant')
            response = json.loads(assistant_msg['content'])
            
            system_msg = next(m for m in data['messages'] if m['role'] == 'system')
            content = system_msg['content']
            dados_start = content.find('{')
            dados_json = content[dados_start:content.rfind('}') + 1]
            dados_classificacao = json.loads(dados_json)
            
            user_msg = next(m for m in data['messages'] if m['role'] == 'user')
            resposta_usuario = user_msg['content']
            
            exemplos.append({
                'id': idx,
                'dados_classificacao': dados_classificacao,
                'resposta_usuario': resposta_usuario,
                'esperado': response
            })
    return exemplos


def parse_habilidades(adequacao_habilidades_str):
    """Parse da string de adequacao_habilidades em dict"""
    result = {}
    pairs = adequacao_habilidades_str.split(', ')
    for pair in pairs:
        hab, val = pair.split(':')
        result[hab] = val
    return result


async def analisar_divergencias():
    """Analisa em detalhe os casos onde houve divergência"""
    print("=" * 100)
    print("ANÁLISE DE DIVERGÊNCIAS - adequacao_macro vs adequacao_habilidades")
    print("=" * 100)
    
    # Carregar todos exemplos
    exemplos = carregar_todos_exemplos('teste_adequacoes.jsonl')
    print(f"\n✓ Carregados {len(exemplos)} exemplos totais")
    
    # Limitar a 100 para análise
    exemplos = exemplos[:100]
    print(f"✓ Analisando primeiros 100 exemplos\n")
    
    # Inicializar cliente
    client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    
    # Coletar resultados
    divergencias = []
    stats_por_habilidade = defaultdict(lambda: {'total': 0, 'acertos': 0})
    
    for idx, exemplo in enumerate(exemplos, 1):
        if idx % 10 == 0:
            print(f"Processando... {idx}/100")
        
        dados = exemplo['dados_classificacao']
        resposta = exemplo['resposta_usuario']
        esperado = exemplo['esperado']
        
        # Executar avaliação
        try:
            system_prompt = f"""Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.
Esses são os dados para classificação: {json.dumps(dados, ensure_ascii=False)}
Considere tambem a resposta do usuario para fazer a classificacao e justificativa."""
            
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": resposta}
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            resultado = json.loads(response.choices[0].message.content.strip())
            
            # Verificar acertos
            macro_correto = resultado.get('adequacao_macro') == esperado['adequacao_macro']
            habilidades_correto = resultado.get('adequacao_habilidades') == esperado['adequacao_habilidades']
            
            # Analisar por habilidade individual
            esperado_habs = parse_habilidades(esperado['adequacao_habilidades'])
            obtido_habs = parse_habilidades(resultado.get('adequacao_habilidades', ''))
            
            for hab_nome, valor_esperado in esperado_habs.items():
                stats_por_habilidade[hab_nome]['total'] += 1
                if obtido_habs.get(hab_nome) == valor_esperado:
                    stats_por_habilidade[hab_nome]['acertos'] += 1
            
            # Se houver divergência entre macro e habilidades
            if not macro_correto and habilidades_correto:
                divergencias.append({
                    'id': exemplo['id'],
                    'teste_num': idx,
                    'esperado_macro': esperado['adequacao_macro'],
                    'obtido_macro': resultado.get('adequacao_macro'),
                    'esperado_habilidades': esperado['adequacao_habilidades'],
                    'obtido_habilidades': resultado.get('adequacao_habilidades'),
                    'habilidades_macro': dados['habilidades_macro'],
                    'nivel_esperado': dados['nivel_esperado'],
                    'nivel_habilidade': dados['nivel_habilidade']
                })
                
        except Exception as e:
            print(f"\nErro no exemplo {idx}: {e}")
            continue
    
    # Relatório
    print("\n" + "=" * 100)
    print("RESULTADOS DA ANÁLISE")
    print("=" * 100)
    
    print(f"\n📊 Estatísticas por habilidade individual:")
    print("-" * 100)
    for hab, stats in sorted(stats_por_habilidade.items()):
        taxa = (stats['acertos'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{hab:45} | {stats['acertos']:3}/{stats['total']:3} | {taxa:6.2f}%")
    
    print(f"\n\n🔍 Casos com divergência (adequacao_habilidades correto MAS adequacao_macro errado):")
    print("-" * 100)
    
    if not divergencias:
        print("\n✅ Nenhuma divergência encontrada! Todos os erros de macro também tiveram erros em habilidades.")
    else:
        for div in divergencias:
            print(f"\n{'='*100}")
            print(f"Teste #{div['teste_num']} (ID {div['id']})")
            print(f"{'='*100}")
            print(f"Nível esperado: {div['nivel_esperado']}")
            print(f"Nível habilidade: {div['nivel_habilidade']}")
            print(f"\nHabilidades macro: {div['habilidades_macro']}")
            print(f"\n❌ MACRO:")
            print(f"   Esperado: {div['esperado_macro']}")
            print(f"   Obtido:   {div['obtido_macro']}")
            print(f"\n✅ HABILIDADES (todas corretas):")
            print(f"   {div['esperado_habilidades']}")
    
    # Verificar se há padrão nos erros de macro
    print(f"\n\n📈 Análise de erros na adequacao_macro:")
    print("-" * 100)
    erros_por_categoria = defaultdict(int)
    for div in divergencias:
        categoria = f"Esperado: {div['esperado_macro']} → Obtido: {div['obtido_macro']}"
        erros_por_categoria[categoria] += 1
    
    if erros_por_categoria:
        print("\nPadrões de erro:")
        for padrao, count in sorted(erros_por_categoria.items(), key=lambda x: -x[1]):
            print(f"  {padrao}: {count} caso(s)")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    import asyncio
    asyncio.run(analisar_divergencias())
