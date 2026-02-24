"""
Script de teste usando exemplos reais do arquivo teste_adequacoes.jsonl
Seleciona 10 casos balanceados (-1, 0, 1) para validar o modelo
"""
import json
import os
from collections import defaultdict
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"
OPENAI_BASE_URL = "https://api.openai.com/v1"


def carregar_exemplos_balanceados(arquivo, quantidade=10):
    """
    Carrega exemplos balanceados por adequacao_macro do arquivo JSONL
    """
    exemplos_por_categoria = defaultdict(list)
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # Extrair a adequacao_macro da resposta do assistant
            assistant_msg = next(m for m in data['messages'] if m['role'] == 'assistant')
            response = json.loads(assistant_msg['content'])
            adequacao_macro = response['adequacao_macro']
            
            # Extrair dados_classificacao do system message
            system_msg = next(m for m in data['messages'] if m['role'] == 'system')
            # O conteúdo tem "Esses são os dados para classificação: {JSON}"
            content = system_msg['content']
            dados_start = content.find('{')
            dados_json = content[dados_start:content.rfind('}') + 1]
            dados_classificacao = json.loads(dados_json)
            
            # Resposta do usuário
            user_msg = next(m for m in data['messages'] if m['role'] == 'user')
            resposta_usuario = user_msg['content']
            
            exemplos_por_categoria[adequacao_macro].append({
                'dados_classificacao': dados_classificacao,
                'resposta_usuario': resposta_usuario,
                'esperado': response
            })
    
    # Balancear: pegar proporcionalmente de cada categoria
    # Tentar 3-4 de cada categoria se possível
    exemplos_selecionados = []
    categorias = ['-1', '0', '1']
    por_categoria = quantidade // len(categorias)
    resto = quantidade % len(categorias)
    
    for i, cat in enumerate(categorias):
        qtd = por_categoria + (1 if i < resto else 0)
        exemplos_selecionados.extend(exemplos_por_categoria[cat][:qtd])
    
    return exemplos_selecionados


async def testar_exemplos():
    """
    Testa o modelo com exemplos do arquivo JSONL
    """
    print("=" * 80)
    print("TESTE COM EXEMPLOS REAIS DO JSONL")
    print("=" * 80)
    
    # Carregar exemplos
    exemplos = carregar_exemplos_balanceados('teste_adequacoes.jsonl', 100)
    print(f"\n✓ Carregados {len(exemplos)} exemplos balanceados\n")
    
    # Inicializar cliente OpenAI
    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )
    
    # Estatísticas
    total = len(exemplos)
    acertos_macro = 0
    acertos_habilidades = 0
    resultados = []
    
    for idx, exemplo in enumerate(exemplos, 1):
        print(f"\n{'='*80}")
        print(f"TESTE {idx}/{total}")
        print(f"{'='*80}")
        
        dados = exemplo['dados_classificacao']
        resposta = exemplo['resposta_usuario']
        esperado = exemplo['esperado']
        
        print(f"\n📋 Dados de entrada:")
        print(f"  - Nível esperado: {dados['nivel_esperado']}")
        print(f"  - Habilidade: {dados['nome_habilidade']}")
        print(f"  - Nível habilidade: {dados['nivel_habilidade']}")
        print(f"  - Grupo: {dados['nome_grupo']}")
        print(f"  - Habilidades macro: {dados['habilidades_macro']}")
        
        print(f"\n💬 Resposta do usuário (primeiros 200 chars):")
        print(f"  {resposta[:200]}...")
        
        print(f"\n🎯 Esperado:")
        print(f"  - adequacao_macro: {esperado['adequacao_macro']}")
        print(f"  - adequacao_habilidades: {esperado['adequacao_habilidades']}")
        
        # Executar avaliação
        try:
            # Construir prompt do sistema
            system_prompt = f"""Você é um avaliador especializado em analisar respostas de usuários para determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta do usuário em três categorias: '1' para nivel de bloom acima do esperado, '0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada para sua classificação, explicando os motivos por trás de sua decisão.
Esses são os dados para classificação: {json.dumps(dados, ensure_ascii=False)}
Considere tambem a resposta do usuario para fazer a classificacao e justificativa."""
            
            # Chamar API
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": resposta}
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            # Extrair resposta
            content = response.choices[0].message.content.strip()
            
            # Tentar parsear JSON
            resultado = json.loads(content)
            
            print(f"\n✨ Obtido:")
            print(f"  - adequacao_macro: {resultado.get('adequacao_macro', 'N/A')}")
            print(f"  - adequacao_habilidades: {resultado.get('adequacao_habilidades', 'N/A')}")
            
            # Verificar acertos
            macro_correto = resultado.get('adequacao_macro') == esperado['adequacao_macro']
            habilidades_correto = resultado.get('adequacao_habilidades') == esperado['adequacao_habilidades']
            
            if macro_correto:
                acertos_macro += 1
                print("\n  ✅ adequacao_macro CORRETO")
            else:
                print("\n  ❌ adequacao_macro INCORRETO")
            
            if habilidades_correto:
                acertos_habilidades += 1
                print("  ✅ adequacao_habilidades CORRETO")
            else:
                print("  ❌ adequacao_habilidades INCORRETO")
            
            resultados.append({
                'teste': idx,
                'macro_correto': macro_correto,
                'habilidades_correto': habilidades_correto,
                'esperado_macro': esperado['adequacao_macro'],
                'obtido_macro': resultado.get('adequacao_macro'),
                'esperado_habilidades': esperado['adequacao_habilidades'],
                'obtido_habilidades': resultado.get('adequacao_habilidades')
            })
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            resultados.append({
                'teste': idx,
                'macro_correto': False,
                'habilidades_correto': False,
                'erro': str(e)
            })
    
    # Resumo final
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    print(f"\nTotal de testes: {total}")
    print(f"Acertos adequacao_macro: {acertos_macro}/{total} ({acertos_macro/total*100:.1f}%)")
    print(f"Acertos adequacao_habilidades: {acertos_habilidades}/{total} ({acertos_habilidades/total*100:.1f}%)")
    
    # Análise por categoria
    print("\n📊 Análise por categoria esperada (adequacao_macro):")
    categorias_esperadas = defaultdict(lambda: {'total': 0, 'acertos': 0})
    for r in resultados:
        if 'erro' not in r:
            cat = r['esperado_macro']
            categorias_esperadas[cat]['total'] += 1
            if r['macro_correto']:
                categorias_esperadas[cat]['acertos'] += 1
    
    for cat in ['-1', '0', '1']:
        info = categorias_esperadas[cat]
        if info['total'] > 0:
            taxa = info['acertos']/info['total']*100
            print(f"  Categoria {cat:>2}: {info['acertos']}/{info['total']} ({taxa:.1f}%)")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(testar_exemplos())
