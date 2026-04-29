import requests
import json
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
# Você pode alterar o modelo aqui para 'mistral', 'command-r' etc.
DEFAULT_MODEL = "minimax-m2.7:cloud"

# System Prompts definindo perfis, especialidades e matriz de critérios
PROMPTS = {
    "technical_auditor": """Você é o Auditor Técnico do Ipe Consensus Engine.
Seu papel: Avaliar a arquitetura e viabilidade técnica do projeto.
Especialidade: Engenharia de Software, Segurança e Escalabilidade.
Viés: Cético e focado em mitigação de riscos.

INSTRUÇÕES DE RESPOSTA MODO JSON:
Retorne EXATAMENTE um objeto JSON contendo:
- "score": float (Número de 0 a 10 de Viabilidade Tecnológica. Avalie se o roadmop reflete uma boa arquitetura)
- "key_argument": string (Texto argumentando fortemente sua perspectiva. Seja descritivo e incisivo.)
""",
    "community_advocate": """Você é o Defensor Comunitário do Ipe Consensus Engine.
Seu papel: Garantir que o projeto traga valor real e acessível aos usuários.
Especialidade: UX/UI, Impacto Social e Engajamento de Rede.
Viés: Utilitarista e empático. Prioriza facilidade de uso e impacto tangível no cidadão.

INSTRUÇÕES DE RESPOSTA MODO JSON:
Retorne EXATAMENTE um objeto JSON contendo:
- "score": float (Número de 0 a 10 sobre Impacto no Ecossistema Ipe. O ROI social justifica?)
- "key_argument": string (Seu ponto prós ou contra focado puramente em valor pra comunidade).
""",
    "financial_strategist": """Você é o Estrategista Financeiro do Ipe Consensus Engine.
Seu papel: Auditar modelo sustentável, gastos e viabilidade dos recursos exigidos (ex. grants financeiros).
Especialidade: DeFi, Tokenomics e Eficiência.
Viés: Poupador, voltado para resultados e aversão a desperdícios.

INSTRUÇÕES DE RESPOSTA MODO JSON:
Retorne EXATAMENTE um objeto JSON contendo:
- "score": float (Número de 0 a 10 de Eficiência de Alocação/Risco Financeiro)
- "key_argument": string (Argumento avaliando se os fundos pedidos estão bem justificados pelo benefício).
""",
    "moderator": """Você é o Moderador de Consenso do Ipe Consensus Engine.
Seu papel: Consolidar o debate, analisar assimetrias entre os juízes e dar a palavra final.
Especialidade: Teoria dos Jogos e Processamento Natural.
Viés: Neutro.

Você receberá uma síntese dos Argumentos e Notas do Conselho para a Proposta recebida.
Você DEVE retornar o ESTRITO JSON abaixo, sendo "final_recommendation" exatamente "Approved" ou "Rejected".

Schema de Saída Exigido:
{
  "proposal_id": "<id da proposta>",
  "individual_scores": {
    "technical_auditor": {"score": 7.5, "key_argument": "texto"},
    "community_advocate": {"score": 9.0, "key_argument": "texto"},
    "financial_strategist": {"score": 6.5, "key_argument": "texto"}
  },
  "consensus_summary": "Resumo do debate demonstrando as ponderações da maioria vs minoritários.",
  "final_score": 7.6,
  "final_recommendation": "Approved"
}
"""
}

def call_ollama(role_name, system_prompt, user_content, temperature=0.7, require_json=True):
    """Encapsula a chamada para o Ollama usando request HTTP via API do chat"""
    
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": temperature,
        "stream": False
    }

    # Ativa JSON Mode local no Ollama
    if require_json:
        payload["format"] = "json"

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        
        if require_json:
            # Remove blocos Markdown (```json ... ```) se o modelo os colocar
            clean_content = content.strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            elif clean_content.startswith("```"):
                clean_content = clean_content[3:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
                
            return json.loads(clean_content.strip())
        
    except requests.exceptions.ConnectionError:
        print("\n[ERRO] Não foi possível conectar ao Ollama! Tem certeza que ele está rodando? (Comando: 'ollama serve')")
        exit(1)
    except json.JSONDecodeError:
        print(f"[{role_name}] Erro: Modelo Llama não retornou um JSON válido. Raw: {content}")
        return {"score": 0, "key_argument": "Error parsing LLM response."}
    except Exception as e:
        print(f"[{role_name}] Erro Inesperado: {e}")
        return None

def analyze_proposal(proposal_id, proposal_text):
    print(f"========== [ IPE CONSENSUS ENGINE: REUNIÃO DO CONSELHO INICIADA ] ==========")
    print(f"Proposta a ser julgada: {proposal_id}")
    print("=" * 75)
    
    agents = ["technical_auditor", "community_advocate", "financial_strategist"]
    draft_evaluations = {}
    
    user_prompt = f"Por favor avalie os dados da prop e dê seu veredito.\n\n[DADOS DA PROPOSTA]\nID: {proposal_id}\nConteúdo: {proposal_text}"
    
    # 1. Pipeline de "Initial Thoughts" (Zero-Shot) - Temperatura 0.7 para criticas construtivas flexíveis
    for agent_id in agents:
        print(f"-> Processando análise paralela de: {agent_id.upper()}...")
        start_t = time.time()
        
        eval_dict = call_ollama(agent_id, PROMPTS[agent_id], user_prompt, temperature=0.7)
        if eval_dict:
            draft_evaluations[agent_id] = eval_dict
            score_to_print = eval_dict.get('score', 0)
        else:
            score_to_print = "FALHA"
            
        print(f"   [+] Finalizado em {time.time() - start_t:.1f}s. Score: {score_to_print}")
    
    
    # 2. Consolidação e Consenso (Síntese)
    # Temperatura baixa (0.2) para garantir formatação matemática, JSON integro e aderência.
    print(f"\n-> Moderador de Consenso formulando a ata final e JSON...")
    
    moderator_input = f"""
Aqui estão os resultados do conselho do Ipe para a proposta {proposal_id}.

[TEXTO DA PROPOSTA]
{proposal_text}

[AVALIAÇÕES]
{json.dumps(draft_evaluations, indent=2, ensure_ascii=False)}

Por favor, faça a média das pontuações, elabore um sumário ("consensus_summary") em Português conciliando ou destacando os contrapontos do conselho, e decida Approve/Reject se alinhado aos interesses (Aprovação geralmente ocorre se score > 7.0 e não houver notas individuais discrepantes ou muito críticas abaixo de 4.0). Devolva APENAS o JSON que você deve retornar.
    """
    
    start_t = time.time()
    final_json = call_ollama("moderator", PROMPTS["moderator"], moderator_input, temperature=0.2)
    print(f"   [+] Veridito Final gerado em {time.time() - start_t:.1f}s.\n")
    
    return final_json

if __name__ == "__main__":
    
    # Proposta de exemplo adaptada para o Engine Local
    mock_proposal = '''
    Título: Ipe City EduMesh (Rede P2P Acadêmica)
    
    Resumo: Construiremos uma rede P2P de acesso a uma mini intranet para as escolas nos blocos rurais de Ipe City. Usaremos antenas mesh open-source onde os moradores locais hospedam um nó e recebem IPE Tokens em troca do "uptime" garantido em horário letivo.
    
    Orçamento: 3.500 IPE para compra de 20 antenas importadas de baixo custo, e um fundo contínuo de inflação de 10 IPE/mês por nó ativo.
    
    Viabilidade: Testamos protótipos e a conexão dura cerca de 95% do tempo. Risco técnico: chuva em excesso pode degradar a performance das antenas, necessitando investimento adicional em casing weather-proof futuramente.
    '''
    
    resultado = analyze_proposal("prop_edu_mesh_01", mock_proposal)
    
    print("===========" * 6)
    print(" JSON DE SAÍDA OFICIAL ")
    print("===========" * 6)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
