"""Test script for the fine-tuned skill evaluator model."""

import asyncio
import os
import sys

# Add src to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from app.ai.agents.skill_evaluator import AgentSkillEvaluator
from app.ai.agents.prompts.skill_evaluator import system_prompt_template


async def test_skill_evaluator():
    """Test the skill evaluator with sample data."""
    
    # Sample data from example.py
    dados_classificacao = {
        "nivel_esperado": "compreender",
        "descricao_nivel_esperado": "Interpretar conceitos-chave com clareza",
        "pergunta_aferidora": "Quais comportamentos voce nota em situacoes de pressao?",
    }
    
    resposta_usuario = (
        "Procuro organizar as informacoes e delegar rapidamente o que cada pessoa precisa fazer. "
        "Tambem revisito dados de experiencias anteriores para antecipar riscos."
    )
    
    # Initialize evaluator with fine-tuned model
    # You can change the model_id here to test different models
    model_id = "ft:gpt-4o-mini-2024-07-18:koru:bloom-evaluator"
    # Or use default model for testing: model_id = "gpt-4o-mini"
    
    print(f"Testing skill evaluator with model: {model_id}")
    print("-" * 80)
    
    try:
        evaluator = AgentSkillEvaluator(
            model_id=model_id,
            system_prompt_template=system_prompt_template,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        
        # Prepare evaluation context (mimicking what agent_orquestrator sends)
        evaluation_context = {
            "user_message": resposta_usuario,
            "current_proficiency_level": dados_classificacao["nivel_esperado"],
            "bloom_levels": {
                "lembrar": {
                    "descricao": "Recordar fatos e conceitos básicos",
                    "acima": "compreender",
                    "abaixo": "lembrar"
                },
                "compreender": {
                    "descricao": dados_classificacao["descricao_nivel_esperado"],
                    "acima": "aplicar",
                    "abaixo": "lembrar"
                },
                "aplicar": {
                    "descricao": "Usar conhecimento em situações práticas",
                    "acima": "analisar",
                    "abaixo": "compreender"
                },
            },
            "rubrics": {
                "Teste": {
                    "compreender": [dados_classificacao["pergunta_aferidora"]]
                }
            },
            "current_specific_skill": "Teste",
            "question": dados_classificacao["pergunta_aferidora"],
        }
        
        print(f"Pergunta: {dados_classificacao['pergunta_aferidora']}")
        print(f"Nível esperado: {dados_classificacao['nivel_esperado']}")
        print(f"Resposta do usuário: {resposta_usuario}")
        print("-" * 80)
        print("Executando avaliação...")
        print()
        
        # Run evaluation
        result = await evaluator.run_evaluation(evaluation_context)
        
        print("Resultado:")
        print(f"  Classificação: {result.output.classificacao}")
        print(f"  Justificativa: {result.output.justificativa}")
        print("-" * 80)
        print("✓ Teste concluído com sucesso!")
        
    except Exception as e:
        print(f"✗ Erro ao testar: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("TESTE DO SKILL EVALUATOR COM MODELO FINE-TUNED")
    print("=" * 80)
    print()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY não encontrada no ambiente!")
        print("Por favor, configure a variável de ambiente OPENAI_API_KEY")
        sys.exit(1)
    
    # Run test
    success = asyncio.run(test_skill_evaluator())
    
    sys.exit(0 if success else 1)
