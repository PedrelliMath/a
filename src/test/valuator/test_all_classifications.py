"""Complete test for all classification values (-1, 0, 1)."""

import asyncio
import json
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT_TEMPLATE = (
    "Você é um avaliador especializado em analisar respostas de usuários para "
    "determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta "
    "do usuário em três categorias: '1' para nivel de bloom acima do esperado, "
    "'0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom "
    "abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada "
    "para sua classificação, explicando os motivos por trás de sua decisão.\n"
    "Esses são os dados para classificação: {dados_classificacao}\n"
    "Considere tambem a resposta do usuario para fazer a classificação e justificativa."
)


async def test_classification(model_id: str, test_name: str, dados: dict, resposta: str):
    """Test a single classification."""
    
    print(f"\n{'='*80}")
    print(f"TESTE: {test_name}")
    print(f"{'='*80}")
    print(f"Nível esperado: {dados['nivel_esperado']}")
    print(f"Resposta: {resposta[:100]}...")
    print("-" * 80)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("✗ OPENAI_API_KEY não encontrada!")
        return None
    
    client = AsyncOpenAI(api_key=api_key)
    
    system_message = SYSTEM_PROMPT_TEMPLATE.format(
        dados_classificacao=json.dumps(dados, ensure_ascii=False)
    )
    
    try:
        completion = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": resposta.strip()},
            ],
        )
        
        response = completion.choices[0].message.content or ""
        
        # Parse response
        try:
            data = json.loads(response)
            if "adequacao_macro" in data:
                classificacao = int(data["adequacao_macro"])
                adequacao_hab = data.get("adequacao_habilidades", "N/A")
                
                print(f"✓ Resposta do modelo:")
                print(f"  adequacao_macro: {classificacao}")
                print(f"  adequacao_habilidades: {adequacao_hab}")
                print("-" * 80)
                
                return classificacao
            else:
                print(f"⚠ Formato inesperado: {response}")
                return None
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"✗ Erro ao parsear: {e}")
            print(f"Resposta: {response}")
            return None
            
    except Exception as e:
        print(f"✗ Erro: {e}")
        return None


async def run_all_tests():
    """Run multiple tests to verify all classification values."""
    
    model_id = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"
    
    print("="*80)
    print("TESTES COMPLETOS DO SKILL EVALUATOR")
    print("="*80)
    
    # Test 1: Below expected (should return -1)
    dados_abaixo = {
        "nivel_esperado": "avaliar",
        "descricao_nivel_esperado": "Avaliar alternativas e tomar decisões fundamentadas",
        "pergunta_aferidora": "Como você avalia diferentes soluções para um problema?",
        "habilidades_macro": {
            "dados_e_inteligencia_artificial": "avaliar",
            "solucao_de_problemas": "avaliar"
        },
        "nome_grupo": "grupo_dados",
        "nome_habilidade": "dados_e_inteligencia_artificial",
        "nivel_habilidade": "avaliar",
        "registro_id": "test_1"
    }
    
    resposta_abaixo = (
        "Eu olho as opcoes e escolho a que parece melhor. "
        "Geralmente confio na minha intuicao."
    )
    
    result1 = await test_classification(
        model_id, 
        "Resposta ABAIXO do esperado (esperado: -1)", 
        dados_abaixo, 
        resposta_abaixo
    )
    
    # Test 2: As expected (should return 0)
    dados_esperado = {
        "nivel_esperado": "aplicar",
        "descricao_nivel_esperado": "Usar conhecimento em situações práticas",
        "pergunta_aferidora": "Como você aplica dados para tomar decisões?",
        "habilidades_macro": {
            "dados_e_inteligencia_artificial": "aplicar",
            "solucao_de_problemas": "aplicar"
        },
        "nome_grupo": "grupo_dados",
        "nome_habilidade": "dados_e_inteligencia_artificial",
        "nivel_habilidade": "aplicar",
        "registro_id": "test_2"
    }
    
    resposta_esperado = (
        "Uso dados do CRM para identificar tendencias de vendas e ajustar "
        "minha abordagem com cada cliente. Por exemplo, analiso historico "
        "de compras antes de fazer uma proposta."
    )
    
    result2 = await test_classification(
        model_id,
        "Resposta NO NÍVEL esperado (esperado: 0)",
        dados_esperado,
        resposta_esperado
    )
    
    # Test 3: Above expected (should return 1)
    dados_acima = {
        "nivel_esperado": "aplicar",
        "descricao_nivel_esperado": "Usar conhecimento em situações práticas",
        "pergunta_aferidora": "Como você aplica dados para tomar decisões?",
        "habilidades_macro": {
            "dados_e_inteligencia_artificial": "aplicar",
            "solucao_de_problemas": "aplicar"
        },
        "nome_grupo": "grupo_dados",
        "nome_habilidade": "dados_e_inteligencia_artificial",
        "nivel_habilidade": "aplicar",
        "registro_id": "test_3"
    }
    
    resposta_acima = (
        "Criei um dashboard no Power BI que cruza dados de CRM, feedback de clientes "
        "e pipeline de vendas. Analiso padroes semanalmente e identifico gargalos antes "
        "que se tornem problemas. Tambem desenvolvi um modelo preditivo que antecipa "
        "churn com 85% de precisao, permitindo acoes preventivas. A equipe usa esses "
        "insights para decisoes estrategicas e ja recuperamos 20% de contas em risco."
    )
    
    result3 = await test_classification(
        model_id,
        "Resposta ACIMA do esperado (esperado: 1)",
        dados_acima,
        resposta_acima
    )
    
    # Summary
    print("\n" + "="*80)
    print("RESUMO DOS TESTES")
    print("="*80)
    
    results = [
        ("Abaixo do esperado", result1, -1),
        ("No nível esperado", result2, 0),
        ("Acima do esperado", result3, 1),
    ]
    
    passed = 0
    failed = 0
    
    for name, result, expected in results:
        if result == expected:
            print(f"✓ {name}: {result} (esperado: {expected})")
            passed += 1
        elif result is not None:
            print(f"⚠ {name}: {result} (esperado: {expected}) - DIFERENTE")
            failed += 1
        else:
            print(f"✗ {name}: ERRO")
            failed += 1
    
    print("-" * 80)
    print(f"Passou: {passed}/{len(results)} | Falhou: {failed}/{len(results)}")
    print("="*80)
    
    return passed == len(results)


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY não encontrada!")
        exit(1)
    
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
