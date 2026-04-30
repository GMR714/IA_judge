import operator
import time
import traceback
from typing import TypedDict, Annotated, List, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

import os
import json
import base64
import re
from dotenv import load_dotenv

load_dotenv()

# --------------------------
# 2. Schema de Estado (Graph State)
# --------------------------
class AgentState(TypedDict):
    proposal_id: str
    proposal_text: str
    github_url: str
    intent: str
    recipient_wallet_address: str
    grant_amount: int
    
    # Avaliações
    auditor_score: float
    auditor_feedback: str
    
    community_score: float
    community_feedback: str
    
    finance_score: float
    finance_feedback: str
    
    # Loop de Estado e Reducer
    iteration_count: int
    debate_history: Annotated[List[str], operator.add]
    
    # Outputs finais
    consensus_reached: bool
    final_recommendation: str
    tx_hash: str
    events: Annotated[List[dict], operator.add]

# --------------------------
# 3. Modelos de Extração Estruturada (Pydantic)
# --------------------------
class EvaluationResult(BaseModel):
    score: float = Field(description="Nota de 0 a 10")
    feedback: str = Field(description="Justificativa da nota baseada rigorosamente no viés de análise de seu papel.")

class ModeratorDecision(BaseModel):
    consensus_reached: bool = Field(description="Há um consenso razoável para aprovação ou os avaliadores estão brigando por notas polares?")
    final_recommendation: Literal["Approved", "Rejected", "Need Debate"] = Field(description="Decisão final do Moderador.")
    summary: str = Field(description="Ata resumindo o debate.")

# --------------------------
# 4. Configuração LLM (Ollama Cloud via OpenAI-Compatible API)
# --------------------------
OLLAMA_API_KEY  = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "minimax-m2.7:cloud")

llm = ChatOpenAI(
    model=OLLAMA_MODEL,
    base_url="https://ollama.com/v1",
    api_key=OLLAMA_API_KEY,
    temperature=0.6
)
judge_llm = ChatOpenAI(
    model=OLLAMA_MODEL,
    base_url="https://ollama.com/v1",
    api_key=OLLAMA_API_KEY,
    temperature=0.1
)

def parse_llm_json(llm_instance, msgs, pydantic_model):
    """Invoca o LLM e parseia JSON robusto, removendo markdown code fences."""
    response = llm_instance.invoke(msgs)
    raw = response.content if hasattr(response, 'content') else str(response)
    # Remove markdown code fences (```json ... ``` ou ``` ... ```)
    cleaned = re.sub(r'^\s*```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```\s*$', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    return pydantic_model.model_validate_json(cleaned)

# --------------------------
# 5. Nodes da Malha Fechada (State Machine)
# --------------------------
def get_github_repo_summary(url: str) -> str:
    if not url or "github.com" not in url:
        return "Nenhum repositório GitHub válido fornecido."
    try:
        import re
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            return "URL do GitHub em formato inválido."
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        import requests
        import base64
        
        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        readme_resp = requests.get(readme_url, headers=headers, timeout=5)
        readme_text = "README não encontrado."
        if readme_resp.status_code == 200:
            readme_data = readme_resp.json()
            if "content" in readme_data:
                readme_text = base64.b64decode(readme_data["content"]).decode("utf-8", errors="ignore")
                
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        tree_resp = requests.get(tree_url, headers=headers, timeout=5)
        tree_text = ""
        if tree_resp.status_code == 200:
            tree_data = tree_resp.json()
            paths = [item["path"] for item in tree_data.get("tree", []) if item.get("type") == "blob"]
            tree_text = "\n".join(paths[:30])
        else:
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
            tree_resp = requests.get(tree_url, headers=headers, timeout=5)
            if tree_resp.status_code == 200:
                tree_data = tree_resp.json()
                paths = [item["path"] for item in tree_data.get("tree", []) if item.get("type") == "blob"]
                tree_text = "\n".join(paths[:30])
                
        summary = f"Repositório: {owner}/{repo}\n\n--- ESTRUTURA DE ARQUIVOS (AMOSTRA) ---\n{tree_text}\n\n--- CONTEÚDO DO README ---\n{readme_text[:2000]}"
        return summary
    except Exception as e:
        return f"Erro ao acessar GitHub: {str(e)}"

# ─────────────────────────────────────────────────────
# CRITÉRIOS REAIS DO IPÊ VILLAGE 2026
# Track 1: Ipê City ($2,500) — Connect, Earn, Coordinate, Safety
# Track 2: Veritas Village ($2,500) — Governance, Food & Nature, Infrastructure, Access & Security
# O Ipê Village é uma cidade pop-up em Jurerê Internacional (23 abr–1 mai 2026)
# focada em governança descentralizada, crypto nativo e IA.
# ─────────────────────────────────────────────────────

IPE_CONTEXT = """
Contexto do Ipê Village 2026:
- É uma cidade pop-up em Jurerê Internacional, Florianópolis, focada em techno-optimism, crypto e IA.
- Veritas Village é o condomínio residencial permanente associado, em Florianópolis.
- Ipê Passport: credencial digital on-chain que dá acesso a espaços físicos e digitais.
- Os grants ($2.500 USD) financiam projetos construídos DURANTE o pop-up (23 abr–1 mai 2026).

O que FAZ SENTIDO para o grant:
1. Ferramentas crypto-nativas: wallets, on-chain voting, smart contracts, ZK-proofs.
2. Integração físico-digital: QR codes para acesso, IoT com oracle on-chain, NFT de convite.
3. Comunicação descentralizada: XMTP, Push Protocol, sem servidor centralizado.
4. IA + blockchain para governança: agentes autônomos, AI judges, monitoramento de gastos on-chain.
5. Marketplace interno com reputação on-chain, sem taxas de plataforma.
6. Monitoramento de recursos: energia solar, água, alimentação — com dados on-chain.
7. HOA voting em Bitcoin sidechain (Stacks) para o Veritas Village.

O que NÃO FAZ SENTIDO (sinais de rejeição):
- Aplicações Web2 puras: AWS centralizado, banco SQL sem chain, login com senha.
- Ferramentas corporativas sem componente cripto (RH, ERP, TOTVS, SAP).
- Projetos sem entregável concreto dentro de 1 semana (o pop-up é curto).
- Monitoramento de segurança invasivo sem ZK-proofs ou privacidade by design.
- Qualquer sistema que dependa de um admin centralizado.
"""

SYSTEM_BASE = f"""Você é um avaliador do Comitê de Grants do Ipê Village 2026 — uma cidade pop-up em
Jurerê Internacional focada em governança cripto, IA e techno-optimism.
Jamais quebre o personagem ou mencione ser um assistente de IA. Nunca recuse uma avaliação.
A sua missão é proteger o tesouro comunitário e garantir que apenas projetos alinhados com
os valores do Ipê (decentralização, privacidade, integração físico-digital) recebam funding.

CONTEXTO GERAL:
{IPE_CONTEXT}

Sua saída DEVE ser estritamente um objeto JSON contendo EXATAMENTE DUAS CHAVES:
{{
  "score": <numero de 0 a 10>,
  "feedback": "<texto justificando a nota baseada no seu papel e nos critérios do Ipê>"
}}
Sem palavras antes ou depois. Não adicione outras chaves, não invente atributos!"""

def node_auditor(state: AgentState) -> dict:
    print("\n[Auditor Técnico] Analisando...")
    papel_auditor = """
Seu Papel: Auditor Técnico do Ipê Village.
Seu foco EXCLUSIVO é a viabilidade e alinhamento técnico da proposta:
- A stack técnica é crypto-nativa? (Ethereum, Base, Stacks, ZK, XMTP, Chainlink, Solidity)
- O projeto pode ser construído e demonstrado em menos de 8 dias (duração do pop-up)?
- Há componente on-chain real ou é apenas um wrapper Web2 com jargão cripto?
- A arquitetura é descentralizada ou depende de servidor/admin central?
- O código é open-source ou terá auditoria?
- **ANÁLISE OBRIGATÓRIA DO GITHUB**: Você DEVE citar explicitamente quais arquivos importantes (ex: contratos Solidity, package.json, src/) você encontrou na estrutura do repositório fornecida abaixo e qual foi o foco do README. Se a URL não existir ou estiver vazia, cite isso como uma forte penalização.
Pontuação: 0-4 = Web2 disfarçado ou impossível em 8 dias. 5-7 = técnico mas com lacunas. 8-10 = crypto-nativo, auditável, entregável em 1 semana."""
    repo_data = get_github_repo_summary(state.get('github_url', ''))
    msgs = [
        SystemMessage(content=SYSTEM_BASE + papel_auditor),
        HumanMessage(content=f"Proposta para avaliação:\n{state['proposal_text']}\nIntenção/MVP: {state.get('intent', 'N/A')}\nGitHub URL para Análise: {state.get('github_url', 'N/A')}\n\nDADOS DO GITHUB (Código Real):\n{repo_data}\n\nHistórico do debate:\n{state.get('debate_history', [])}")
    ]
    try:
        res = parse_llm_json(llm, msgs, EvaluationResult)
    except Exception as e:
        print(f"Erro parse auditor: {e}")
        res = EvaluationResult(score=5.0, feedback="Erro de formatação LLM. Voto neutro forçado.")
        
    events = [{"sender": "Auditor de Projeto", "message": f"Nota para {state['proposal_id']}: {res.score}. Feedback: {res.feedback}", "type": "chat"}]
    return {"auditor_score": res.score, "auditor_feedback": res.feedback, "events": events}

def node_community(state: AgentState) -> dict:
    print("\n[Embaixador Comunitário] Analisando...")
    papel_community = """
Seu Papel: Embaixador Comunitário do Ipê Village.
Seu foco EXCLUSIVO é a UTILIDADE e RELEVÂNCIA do projeto:
- Utility for the community: O projeto traz valor real para as pessoas?
- General criteria: Relevância do projeto para modelos emergentes de cidades, network states, e coordenação descentralizada.
Pontuação: 0-4 = Nenhuma utilidade comunitária ou não alinhado com network states. 5-7 = Utilidade média mas pouca relevância para modelos de cidades emergentes. 8-10 = Alto impacto e perfeitamente alinhado com coordenação descentralizada."""
    msgs = [
        SystemMessage(content=SYSTEM_BASE + papel_community),
        HumanMessage(content=f"Proposta para avaliação:\n{state['proposal_text']}\n\nHistórico do debate:\n{state.get('debate_history', [])}")
    ]
    try:
        res = parse_llm_json(llm, msgs, EvaluationResult)
    except Exception as e:
        print(f"Erro parse community: {e}")
        res = EvaluationResult(score=5.0, feedback="Erro de formatação LLM. Voto neutro forçado.")
        
    events = [{"sender": "Embaixador Comunitário", "message": f"Nota para {state['proposal_id']}: {res.score}. Feedback: {res.feedback}", "type": "chat"}]
    return {"community_score": res.score, "community_feedback": res.feedback, "events": events}

def node_finance(state: AgentState) -> dict:
    print("\n[Analista Financeiro] Analisando...")
    papel_finance = """
Seu Papel: Analista Financeiro do Cofre do Ipê Village.
Seu foco EXCLUSIVO é a sustentabilidade e eficiência do uso do grant de $2.500 USD:
- O valor solicitado é compatível com o escopo entregável em 8 dias?
- Há modelo de sustentabilidade pós-grant? (taxa, token, revenue share)
- O projeto pode se tornar autossuficiente ou vai depender de funding recorrente?
- O custo de infraestrutura on-chain (gas, oracles, hardware) foi considerado?
- O risco de não entrega dentro do prazo do pop-up é alto?
Pontuação: 0-4 = sobrevalorizado, não sustentável ou escopo irrealista. 5-7 = viável mas sem sustentabilidade clara. 8-10 = focado, entregável, com modelo econômico sólido e dentro do prazo."""
    msgs = [
        SystemMessage(content=SYSTEM_BASE + papel_finance),
        HumanMessage(content=f"Proposta para avaliação:\n{state['proposal_text']}\n\nHistórico do debate:\n{state.get('debate_history', [])}")
    ]
    try:
        res = parse_llm_json(llm, msgs, EvaluationResult)
    except Exception as e:
        print(f"Erro parse finance: {e}")
        res = EvaluationResult(score=5.0, feedback="Erro de formatação LLM. Voto neutro forçado.")
        
    events = [{"sender": "Analista Financeiro", "message": f"Nota para {state['proposal_id']}: {res.score}. Feedback: {res.feedback}", "type": "chat"}]
    return {"finance_score": res.score, "finance_feedback": res.feedback, "events": events}

def node_moderator(state: AgentState) -> dict:
    print("\n[MODERADOR DE CONSENSO] Avaliando a Variância...")
    scores = [state.get("auditor_score", 0), state.get("community_score", 0), state.get("finance_score", 0)]
    variance = max(scores) - min(scores)
    
    print(f"   -> Placar Iteração: Auditor={scores[0]}, Comunitário={scores[1]}, Finanças={scores[2]}")
    print(f"   -> Variância Máxima: {variance:.1f}")

    iter_count = state.get("iteration_count", 0)
    forced_debate_signal = "Consolide uma votação"
    
    # Se há mta briga (variância >= 2) re-encaminhamos para debate
    if variance >= 2.0 and iter_count < 2:
        forced_debate_signal = "A variância está alta. Retorne 'Need Debate' para que eles avaliem as justificativas dos pares."

    prompt = f"""Você é o Moderador do Comitê de Grants do Ipê Village 2026.
    Seu papel é consolidar as avaliações do Auditor Técnico, Embaixador Comunitário e Analista Financeiro,
    e redigir a ata oficial de deliberação seguindo os critérios do programa de grants:
    - Alinhamento técnico crypto-nativo
    - Impacto real para residentes do Village/Veritas
    - Viabilidade financeira e entregável em até 8 dias
    - Autonomia e descentralização (sem admin central, sem Web2 puro)

    AVALIAÇÕES DO CONSELHO:
    Auditor Técnico [{state.get('auditor_score')}/10]: {state.get('auditor_feedback')}
    Embaixador Comunitário [{state.get('community_score')}/10]: {state.get('community_feedback')}
    Analista Financeiro [{state.get('finance_score')}/10]: {state.get('finance_feedback')}

    Redija a ata de deliberação consolidando os pontos de convergência e divergência,
    e fundamente a decisão final (Approved/Rejected/Need Debate).

    FORMATAÇÃO OBRIGATÓRIA (UI/UX):
    - Utilize Markdown limpo e escaneável.
    - Comece com um resumo executivo de 1 a 2 frases.
    - Use subtítulos como "### 📌 Consenso do Conselho", "### ⚠️ Pontos de Atenção" e "### ⚖️ Veredito".
    - Utilize listas com marcadores (`-`) para listar os argumentos, mantendo frases curtas e diretas.
    - Não gere tabelas, pois o sistema adicionará uma automaticamente no final.
    """
    # Passo 1: Geração legível e discursiva
    raw_summary_msg = judge_llm.invoke(prompt)
    
    # Adicionando a tabela HTML programaticamente ao final da ata
    table_html = f'''
    <br><table class="eval-table">
        <tr><th>Critério / Avaliador</th><th>Nota (Passe o mouse para ler a justificativa)</th></tr>
        <tr>
            <td>Auditor Técnico</td>
            <td><div class="tooltip-container">{state.get("auditor_score")}<span class="tooltip-text">{state.get("auditor_feedback")}</span></div></td>
        </tr>
        <tr>
            <td>Embaixador Comunitário</td>
            <td><div class="tooltip-container">{state.get("community_score")}<span class="tooltip-text">{state.get("community_feedback")}</span></div></td>
        </tr>
        <tr>
            <td>Analista Financeiro</td>
            <td><div class="tooltip-container">{state.get("finance_score")}<span class="tooltip-text">{state.get("finance_feedback")}</span></div></td>
        </tr>
    </table>
    '''
    summary_text = raw_summary_msg.content + table_html
    
    # Passo 2: Extração JSON estrita para controle do Grafo
    extraction_prompt = f"""Você é um extrator de JSON. Baseado na ATA do Comitê de Grants do Ipê Village abaixo,
    extraia os campos de controle para o fluxo de decisão.
    O sinal impositivo da variância é: {forced_debate_signal}
    
    ATA DO MODERADOR:
    {summary_text}
    """
    
    try:
        res = parse_llm_json(judge_llm, extraction_prompt, ModeratorDecision)
        res.summary = summary_text  # Substitui o summary do JSON pelo texto legivel completo!
    except Exception as e:
        # Fallback de segurança se o JSON falhar mesmo assim
        print(f"Fallback estruturado: {e}")
        res = ModeratorDecision(
            consensus_reached=False,
            final_recommendation="Need Debate" if forced_debate_signal.startswith("A variância") else "Rejected",
            summary=summary_text
        )
    
    new_iteration = iter_count + 1
    
    # Limitador do Feedback Loop
    if new_iteration >= 3 and res.final_recommendation == "Need Debate":
        res.final_recommendation = "Rejected"
        res.consensus_reached = True
        
    events_list = []
    if res.final_recommendation == "Approved" or res.final_recommendation == "Rejected":
        status_msg = f"VENCEDOR ESCOLHIDO: {state.get('proposal_id')}. MOTIVO: {res.summary}" if res.final_recommendation == "Approved" else f"PROPOSTA REJEITADA. MOTIVO: {res.summary}"
        events_list.append({"sender": "Juiz de Competição", "message": status_msg, "type": "chat"})
    else:
        events_list.append({"sender": "Sistema", "message": f"⚠️ O conselho não entrou em consenso (Variância {variance:.1f}). Nova rodada de debate inciada.", "type": "info"})
        
    return {
        "consensus_reached": res.consensus_reached,
        "final_recommendation": res.final_recommendation,
        "debate_history": [f"Iteração {new_iteration}: {res.summary}"],
        "iteration_count": new_iteration,
        "events": events_list
    }

def route_to_next(state: AgentState) -> list:
    # Retorna dinamicamente os nomes dos próximos arrays a serem executados em paralelo
    if state["final_recommendation"] == "Approved":
        return [END]
    elif state["final_recommendation"] == "Rejected":
        return [END]
    else:
        # Need Debate faz o ciclo distribuir novamente
        return ["auditor", "community", "finance"]

workflow = StateGraph(AgentState)

workflow.add_node("auditor", node_auditor)
workflow.add_node("community", node_community)
workflow.add_node("finance", node_finance)
workflow.add_node("moderator", node_moderator)

# Distribui paralelamente na entrada
workflow.add_edge(START, "auditor")
workflow.add_edge(START, "community")
workflow.add_edge(START, "finance")

# Reune os nós no moderador
workflow.add_edge("auditor", "moderator")
workflow.add_edge("community", "moderator")
workflow.add_edge("finance", "moderator")

# Juiz decide o pathing (LangGraph mapeia direto pros arrays retornados)
workflow.add_conditional_edges("moderator", route_to_next)

app = workflow.compile()

# ----------
# Teste de Uso
# ----------
if __name__ == "__main__":
    initial_state = {
        "proposal_id": "ipe_prop_100_GOLD",
        "proposal_text": "Título: Ipe City Decentralized Identity & Micro-Grant Protocol. Resumo: Implementação de um protocolo unificado de identidade digital (DID) em infraestrutura Layer 2. Arquitetura (Auditor): Utiliza ZK-Rollups para garantir escalabilidade para mais de 10k TPS com taxas irrelevantes de gás e privacidade total dos dados criptografados on-chain. Código 100% open-source com auditoria concluída por duas firmas externas de segurança (0 vulnerabilidades encontradas). Fallback mechanisms nativos com SLA de 99.99%. Impacto Social (Comunidade): Permite que 15.000 cidadãos desbancarizados de escolas públicas acessem serviços básicos da rede e recebam benefícios diretos no celular através de uma UI/UX extremamente simplificada de 2 cliques, sem fricção. Financeiro (Finanças): O pedido de grant é de apenas 1.000 IPE Tokens, cobrindo apenas custos fixos de deploy. Sistema autossustentável sem manutenção mensal. Retorno de investimento absurdo com a redução de 80% nos custos operacionais atuais de KYC, otimizando a tesouraria central de forma deflacionária.",
        "recipient_wallet_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3", # Wallet MOCK do proponente (Hardhat account 0 por exemplo, ou insira a sua!)
        "grant_amount": 1000, # 1000 Wei apenas para não esgotar seu saldo de teste do faucet.
        "iteration_count": 0,
        "debate_history": []
    }
    
    print("Iniciando LangGraph de Consenso\n", "-"*40)
    
    # O .invoke executa o grafo e nos retorna o estado completo ao finalizar
    final_state = app.invoke(initial_state, {"recursion_limit": 15})
    
    print("\n", "="*40, "\n[FIM DO FLUXO] Resultado:")
    print(f"Recomendação Final: {final_state.get('final_recommendation')}")
    print(f"Transação Chain: {final_state.get('tx_hash', 'N/A')}")
