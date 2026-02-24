"""Simple standalone test for the fine-tuned skill evaluator model - NEW FORMAT."""

import asyncio
import json
import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables from .env
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


async def test_new_format():
    """Test the skill evaluator with new format (matching example.py)."""
    
    # Sample data matching example.py format
    dados_classificacao = {
        "nivel_esperado": "avaliar",
        "descricao_nivel_esperado": (
            "compara abordagens de solucao e seleciona a mais eficaz com base em dados. / "
            "avalia impacto da experiencia na fidelizacao e resultados de negocio. / "
            "avalia a eficacia da tomada de decisao baseada em dados estrategicos."
        ),
        "pergunta_aferidora": (
            "como voce avaliou diferentes solucoes para um problema estrategico? / "
            "como voce mede o impacto de uma melhoria na experiencia do cliente? / "
            "como voce valida se uma decisao baseada em dados deu resultado?"
        ),
        "habilidades_macro": {
            "dados_e_inteligencia_artificial": "analisar",
            "fluencia_digital": "aplicar",
            "solucao_de_problemas": "analisar"
        },
        "nome_grupo": "grupo_01",
        "nome_habilidade": "dados_e_inteligencia_artificial",
        "nivel_habilidade": "analisar",
        "registro_id": "test_14"
    }
    
    resposta_usuario = (
        "em uma ocasiao, nosso time enfrentava queda nas vendas em contas-chave. "
        "para entender a raiz, consolidei dados do crm e de feedbacks, "
        "cruzando informacoes de pipeline, taxas de conversao e ciclos de decisao. "
        "estruturei paineis no power bi, facilitando a visualizacao de gargalos. "
        "a equipe passou a revisitar dados semanalmente, ajustando abordagens conforme "
        "tendencias identificadas. como resultado, recuperamos 18% de contas em risco em dois meses. "
        "mantive o monitoramento via dashboards e sessoes quinzenais de analise. "
        "o diferencial foi engajar todos na leitura de dados, promovendo decisoes colaborativas "
        "e antecipando problemas de maneira inovadora."
    )
    
    # Model ID - fine-tuned model
    model_id = "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5"
    
    print(f"Testing with model: {model_id}")
    print("-" * 80)
    
    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("✗ OPENAI_API_KEY não encontrada!")
        return False
    
    client = AsyncOpenAI(api_key=api_key)
    
    # Build system message
    system_message = SYSTEM_PROMPT_TEMPLATE.format(
        dados_classificacao=json.dumps(dados_classificacao, ensure_ascii=False)
    )
    
    print(f"Pergunta: {dados_classificacao['pergunta_aferidora'][:80]}...")
    print(f"Nível esperado: {dados_classificacao['nivel_esperado']}")
    print(f"Habilidades macro: {list(dados_classificacao['habilidades_macro'].keys())}")
    print(f"Resposta do usuário: {resposta_usuario[:100]}...")
    print("-" * 80)
    print("Executando avaliação...")
    print()
    
    try:
        # Call OpenAI
        completion = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": resposta_usuario.strip()},
            ],
        )
        
        response = completion.choices[0].message.content or ""
        
        print("Resposta do modelo:")
        print(response)
        print("-" * 80)
        
        # Parse response - NEW FORMAT
        classificacao = 0
        justificativa = response.strip()
        
        try:
            data = json.loads(response)
            
            # NEW FORMAT: adequacao_macro is the main classification
            if "adequacao_macro" in data:
                classificacao = int(data["adequacao_macro"])
                
                # Build justification from adequacao_habilidades
                if "adequacao_habilidades" in data:
                    justificativa = f"Avaliação das habilidades: {data['adequacao_habilidades']}"
                else:
                    justificativa = "Classificação baseada na adequação macro"
                
                classificacao = max(-1, min(1, classificacao))
                
                print(f"\n✓ Formato NOVO encontrado!")
                print(f"  adequacao_macro: {data['adequacao_macro']}")
                print(f"  adequacao_habilidades: {data.get('adequacao_habilidades', 'N/A')}")
            else:
                print(f"\n⚠ Formato diferente do esperado")
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"\n⚠ Erro ao parsear JSON: {e}")
            justificativa = response
        
        print(f"\nClassificação extraída: {classificacao}")
        print(f"Justificativa: {justificativa}")
        print("-" * 80)
        print("✓ Teste concluído com sucesso!")
        
        return True
        
    except Exception as e:
        print(f"✗ Erro ao testar: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("TESTE DO SKILL EVALUATOR - NOVO FORMATO")
    print("=" * 80)
    print()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY não encontrada no ambiente!")
        print("Por favor, configure a variável de ambiente OPENAI_API_KEY")
        exit(1)
    
    success = asyncio.run(test_new_format())
    exit(0 if success else 1)
