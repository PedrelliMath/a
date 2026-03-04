import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Dados de entrada
dados = {
    "nivel_esperado": "avaliar",
    "descricao_nivel_esperado": "compara abordagens de solucao e seleciona a mais eficaz com base em dados. / avalia impacto da experiencia na fidelizacao e resultados de negocio. / avalia a eficacia da tomada de decisao baseada em dados estrategicos.",
    "pergunta_aferidora": "como voce avaliou diferentes solucoes para um problema estrategico? / como voce mede o impacto de uma melhoria na experiencia do cliente? / como voce valida se uma decisao baseada em dados deu resultado?",
    "habilidades_macro": {
        "dados_e_inteligencia_artificial": "analisar",
        "fluencia_digital": "aplicar",
        "solucao_de_problemas": "analisar"
    },
    "nome_grupo": "grupo_01",
    "nome_habilidade": "dados_e_inteligencia_artificial",
    "nivel_habilidade": "analisar",
    "registro_id": "14"
}

resposta_usuario = (
    "em uma ocasiao, nosso time enfrentava queda nas vendas em contas-chave. para entender a raiz, consolidei dados do crm e de feedbacks, "
    "cruzando informacoes de pipeline, taxas de conversao e ciclos de decisao. estruturei paineis no power bi, facilitando a visualizacao de gargalos. "
    "a equipe passou a revisitar dados semanalmente, ajustando abordagens conforme tendencias identificadas. como resultado, recuperamos 18% de contas em risco em dois meses. "
    "mantive o monitoramento via dashboards e sessoes quinzenais de analise. o diferencial foi engajar todos na leitura de dados, promovendo decisoes colaborativas e antecipando problemas de maneira inovadora."
)

# Montar mensagens
system_message = (
    "Você é um avaliador especializado em analisar respostas de usuários para "
    "determinar o nível de bloom demonstrado. Sua tarefa é classificar a resposta "
    "do usuário em três categorias: '1' para nivel de bloom acima do esperado, "
    "'0' para um nível de bloom igual ao esperado e '-1' para um nível de bloom "
    "abaixo do esperado. Além disso, você deve fornecer uma justificativa detalhada "
    "para sua classificação, explicando os motivos por trás de sua decisão.\n"
    f"Esses são os dados para classificação: {json.dumps(dados, ensure_ascii=False)}\n"
    "Considere tambem a resposta do usuario para fazer a classificação e justificativa."
)

# Chamar o modelo
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
completion = client.chat.completions.create(
    model="ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5",
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": resposta_usuario},
    ],
)

# Retornar apenas o resultado do modelo
print(completion.choices[0].message.content)
