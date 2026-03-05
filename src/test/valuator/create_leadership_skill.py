#!/usr/bin/env python3
"""
Script para criar a skill de Liderança no banco local
"""
import requests
import json
import os
from dotenv import load_dotenv

# Configurações
KEYCLOAK_URL = "http://200.137.197.134:18080"
API_BASE_URL = "http://localhost:8000/api/v1"
REALM = "ceia"
CLIENT_ID = "chatbot-frontend"



def get_token():
    """Obtém token do Keycloak"""
    print("🔑 Obtendo token do Keycloak...")
    
    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    
    #pegar username e password do arquivo .env
    load_dotenv()
    USERNAME = os.getenv("USERNAME")
    PASSWORD = os.getenv("PASSWORD")
    
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": USERNAME,
        "password": PASSWORD,
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        print("✅ Token obtido com sucesso!")
        return token_data["access_token"]
    else:
        print(f"❌ Erro ao obter token: {response.status_code}")
        print(response.text)
        return None

def create_leadership_skill(token):
    """Cria a skill de Liderança"""
    print("\n📝 Criando skill de Liderança...")
    
    url = f"{API_BASE_URL}/skills/"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    skill_data = {
        "name": "Liderança",
        "description": "Avaliação de competências de liderança, incluindo capacidade de inspirar equipes, tomar decisões estratégicas, desenvolver pessoas e criar uma cultura de alto desempenho.",
        "questions": {
            "rubrics": {
                "Inspiração e Visão, Desenvolvimento de Pessoas, Tomada de Decisão": {
                    "lembrar": [
                        "Qual foi a última vez que você inspirou sua equipe a alcançar um objetivo?",
                        "Quais práticas você usa para desenvolver as pessoas do seu time?",
                        "Que decisões difíceis você já precisou tomar como líder?"
                    ],
                    "compreender": [
                        "Como você explicaria a importância de uma visão clara para o time?",
                        "Por que investir no desenvolvimento de pessoas é importante para resultados?",
                        "Como você analisa uma situação antes de tomar uma decisão estratégica?"
                    ],
                    "aplicar": [
                        "Como você aplica sua visão de liderança no dia a dia?",
                        "Que ações práticas você implementou para desenvolver seu time?",
                        "Como você toma decisões em situações de alta pressão?"
                    ],
                    "analisar": [
                        "Como você identifica e desenvolve potenciais líderes na sua equipe?",
                        "Como você analisa o impacto das suas decisões no time e nos resultados?",
                        "Como você divide desafios complexos para sua equipe resolver?"
                    ],
                    "avaliar": [
                        "Como você avalia a eficácia do seu estilo de liderança?",
                        "Como você mede o desenvolvimento e crescimento do seu time?",
                        "Como você valida se suas decisões estratégicas deram resultado?"
                    ],
                    "criar": [
                        "Que modelos ou frameworks de liderança você já criou ou adaptou?",
                        "Que inovações você trouxe para desenvolver pessoas?",
                        "Como você cria uma cultura de inovação e alto desempenho?"
                    ]
                },
                "Comunicação, Gestão de Conflitos, Accountability": {
                    "lembrar": [
                        "Quais situações de conflito você já mediou?",
                        "Como você garante que sua equipe assuma responsabilidade?",
                        "Que práticas de comunicação você considera essenciais?"
                    ],
                    "compreender": [
                        "Por que comunicação transparente é importante na liderança?",
                        "Como conflitos podem ser oportunidades de crescimento?",
                        "O que significa accountability para você?"
                    ],
                    "aplicar": [
                        "Como você aplica princípios de comunicação não-violenta?",
                        "Que técnicas você usa para resolver conflitos na equipe?",
                        "Como você estabelece accountability no seu time?"
                    ],
                    "analisar": [
                        "Como você identifica as causas raiz de conflitos recorrentes?",
                        "Como você analisa falhas de comunicação e as corrige?",
                        "Como você detecta quando alguém não está assumindo responsabilidade?"
                    ],
                    "avaliar": [
                        "Como você avalia a qualidade da comunicação no seu time?",
                        "Como você mede a maturidade da equipe em lidar com conflitos?",
                        "Como você valida se a cultura de accountability está funcionando?"
                    ],
                    "criar": [
                        "Que processos de feedback você criou para seu time?",
                        "Como você constrói uma cultura de comunicação aberta?",
                        "Que sistemas você desenvolveu para garantir accountability?"
                    ]
                },
                "Gestão de Mudanças, Resiliência, Empoderamento": {
                    "lembrar": [
                        "Qual foi a última grande mudança que você liderou?",
                        "Como você demonstra resiliência em momentos difíceis?",
                        "De que formas você empodera sua equipe?"
                    ],
                    "compreender": [
                        "Por que a gestão de mudanças é um desafio de liderança?",
                        "Como resiliência se relaciona com efetividade na liderança?",
                        "O que significa realmente empoderar pessoas?"
                    ],
                    "aplicar": [
                        "Como você conduziu uma mudança significativa na organização?",
                        "Que práticas você usa para manter a resiliência do time?",
                        "Como você delega poder de decisão para sua equipe?"
                    ],
                    "analisar": [
                        "Como você identifica resistências a mudanças e as trabalha?",
                        "Como você analisa e fortalece a resiliência organizacional?",
                        "Como você avalia o nível de autonomia que sua equipe tem?"
                    ],
                    "avaliar": [
                        "Como você avalia o sucesso de uma iniciativa de mudança?",
                        "Como você mede a capacidade de resiliência do time?",
                        "Como você valida se está realmente empoderando pessoas?"
                    ],
                    "criar": [
                        "Que metodologias de gestão de mudanças você já desenvolveu?",
                        "Como você cria ambientes que fomentam resiliência?",
                        "Que estruturas você criou para aumentar autonomia do time?"
                    ]
                }
            },
            "bloom_levels": {
                "lembrar": {
                    "descricao": "Capacidade de recordar informações, fatos e conceitos básicos. Inclui identificar, listar e descrever elementos conhecidos.",
                    "acima": "compreender",
                    "abaixo": "lembrar"
                },
                "compreender": {
                    "descricao": "Capacidade de interpretar e explicar conceitos. Inclui classificar, comparar, exemplificar e resumir ideias.",
                    "acima": "aplicar",
                    "abaixo": "lembrar"
                },
                "aplicar": {
                    "descricao": "Capacidade de usar conhecimento em situações concretas. Inclui executar, implementar e resolver problemas práticos.",
                    "acima": "analisar",
                    "abaixo": "compreender"
                },
                "analisar": {
                    "descricao": "Capacidade de dividir informações em partes e encontrar relações. Inclui diferenciar, organizar e investigar conexões.",
                    "acima": "avaliar",
                    "abaixo": "aplicar"
                },
                "avaliar": {
                    "descricao": "Capacidade de fazer julgamentos fundamentados com base em critérios definidos. Inclui analisar alternativas, justificar escolhas e medir resultados.",
                    "acima": "criar",
                    "abaixo": "analisar"
                },
                "criar": {
                    "descricao": "Capacidade de gerar novas ideias, produtos ou processos. Envolve planejar, produzir e desenvolver soluções originais a partir de conhecimentos diversos.",
                    "acima": "criar",
                    "abaixo": "avaliar"
                }
            }
        },
        "agents_config": {
            "supervisor": {
                "model_name": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "question_generator": {
                "model_name": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "question_regenerator": {
                "model_name": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "skill_evaluator": {
                "model_name": "ft:gpt-4o-mini-2024-07-18:projeto-koru:bloom-evaluator:D3a4Fxf5",
                "temperature": 0.3,
                "max_tokens": 1000
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=skill_data)
    
    if response.status_code == 201:
        skill = response.json()
        print("✅ Skill criada com sucesso!")
        print(f"\n📋 Detalhes da Skill:")
        print(f"   ID: {skill['id']}")
        print(f"   Nome: {skill['name']}")
        print(f"   Descrição: {skill['description']}")
        print(f"   Criada em: {skill['created_at']}")
        return skill
    else:
        print(f"❌ Erro ao criar skill: {response.status_code}")
        print(response.text)
        return None

def main():
    print("🚀 Iniciando criação da skill de Liderança\n")
    
    # 1. Obter token
    token = get_token()
    if not token:
        print("\n❌ Falha ao obter token. Abortando...")
        return
    
    # 2. Criar skill
    skill = create_leadership_skill(token)
    
    if skill:
        print("\n✨ Processo concluído com sucesso!")
        print(f"\n💡 Use este ID para criar sessões: {skill['id']}")
    else:
        print("\n❌ Falha ao criar skill.")

if __name__ == "__main__":
    main()
