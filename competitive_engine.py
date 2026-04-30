import sys
if sys.platform == 'win32' and sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')

import operator
import time
import traceback
from typing import TypedDict, Annotated, List, Literal, Optional
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
# 2. Schema de Estado (Batch State)
# --------------------------
class Proposal(BaseModel):
    proposal_id: str = Field(description="ID único da proposta")
    proposal_text: str = Field(description="Texto descritivo da proposta")
    recipient_wallet_address: str = Field(description="Endereço da carteira do proponente")
    grant_amount: int = Field(description="Valor do prêmio solicitado (em Wei)")
    intent: str = Field(default="", description="Intenção/MVP da proposta")
    github_url: str = Field(default="", description="URL do repositório GitHub")
    
    # Avaliações (preenchidas durante o fluxo)
    auditor_score: float = 0.0
    auditor_feedback: str = ""
    community_score: float = 0.0
    community_feedback: str = ""
    finance_score: float = 0.0
    finance_feedback: str = ""
    
    @property
    def average_score(self):
        return (self.auditor_score + self.community_score + self.finance_score) / 3

class BatchState(TypedDict):
    proposals: List[Proposal]
    winner: Proposal
    final_reasoning: str
    tx_hash: str
    events: Annotated[List[dict], operator.add]

# --------------------------
# 3. Modelos de Extração Estruturada (Pydantic)
# --------------------------
class EvaluationResult(BaseModel):
    score: float = Field(description="Nota de 0 a 10")
    feedback: str = Field(description="Justificativa da nota baseada rigorosamente no viés de análise de seu papel.")

class CompetitionDecision(BaseModel):
    winner_id: str = Field(description="O ID da proposta vencedora. Use 'NONE' se todas forem rejeitadas.")
    reasoning: str = Field(description="Justificativa técnica de por que esta proposta superou as outras.")

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
# --------------------------
# 5. Nodes da Competição
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
# ─────────────────────────────────────────────────────

IPE_CONTEXT = """
Contexto do Ipê Village 2026:
- Cidade pop-up em Jurerê Internacional, Florianópolis, 23 abr–1 mai 2026.
- Foco: techno-optimism, crypto nativo, IA e governança descentralizada.
- Critério Geral de Avaliação (🥇): Relevância do projeto para modelos emergentes de cidades, network states e coordenação descentralizada.

FAZ SENTIDO para o grant (pontua mais):
- Projetos com forte foco em Produto, Qualidade Técnica e Inovação.
- Utilidade clara para a comunidade local e alinhamento com coordenação descentralizada.
- Proponentes que demonstram Presença, Colaboração e Compartilhamento de Conhecimento.
"""

SYSTEM_BASE = f"""Você é avaliador no Torneio de Grants do Ipê Village 2026 — cidade pop-up em Jurerê Internacional
focada em governança cripto, IA e techno-optimism. MULTIPLE propostas estão DISPUTANDO um único prêmio.
Jamais quebre o personagem ou mencione ser um assistente de IA. Nunca recuse uma avaliação.
Proteja o tesouro: financie apenas projetos que realmente se alinham com os valores do Ipê.

CONTEXTO:
{IPE_CONTEXT}

Sua saída para CADA avaliação deve ser estritamente um objeto JSON com:
{{
  "score": <numero de 0 a 10>,
  "feedback": "<justificativa baseada no seu papel e nos critérios do Ipê>"
}}"""

def node_auditor_batch(state: BatchState) -> dict:
    events = [{"sender": "Auditor Técnico", "message": f"Iniciando auditoria técnica de {len(state['proposals'])} propostas pelo critério do Ipê Village...", "type": "info"}]
    updated_proposals = []
    papel_auditor = """
Seu Papel: Auditor Técnico do Ipê Village (Torneio).
Avalie cada proposta pelo critério técnico do programa de grants:
- Stack é crypto-nativa (Ethereum/Base, Stacks, ZK, XMTP, Chainlink, Solidity)?
- Entregouável real em 8 dias de pop-up?
- A arquitetura é descentralizada ou depende de servidor/admin central?
- O código é open-source ou terá auditoria?
- **ANÁLISE OBRIGATÓRIA DO GITHUB**: Você DEVE citar explicitamente quais arquivos importantes (ex: contratos Solidity, package.json, src/) você encontrou na estrutura do repositório fornecida abaixo e qual foi o foco do README. Se a URL não existir ou estiver vazia, cite isso como uma forte penalização.
De nota 0 para Web2 puro sem on-chain. Penalize fortemente aplicações AWS/SQL/ERP centralizadas."""
    for prop in state['proposals']:
        print(f"   -> Avaliando: {prop.proposal_id}")
        repo_data = get_github_repo_summary(prop.github_url)
        msgs = [
            SystemMessage(content=SYSTEM_BASE + papel_auditor),
            HumanMessage(content=f"Proposta para avaliação técnica:\n{prop.proposal_text}\nIntenção/MVP: {prop.intent}\nGitHub URL: {prop.github_url}\n\nDADOS DO GITHUB (Código Real):\n{repo_data}")
        ]
        res = llm.with_structured_output(EvaluationResult).invoke(msgs)
        prop.auditor_score = res.score
        prop.auditor_feedback = res.feedback
        updated_proposals.append(prop)
        events.append({"sender": "Auditor Técnico", "message": f"Nota para {prop.proposal_id}: {res.score}. Feedback: {res.feedback}", "type": "chat"})
    return {"proposals": updated_proposals, "events": events}

def node_community_batch(state: BatchState) -> dict:
    events = [{"sender": "Embaixador Comunitário", "message": f"Avaliando impacto comunitário de {len(state['proposals'])} propostas...", "type": "info"}]
    updated_proposals = []
    papel_community = """
Seu Papel: Embaixador Comunitário do Ipê Village (Torneio).
Avalie a UTILIDADE e RELEVÂNCIA do projeto:
- Utility for the community: O projeto traz valor real para as pessoas?
- General criteria: Relevância do projeto para modelos emergentes de cidades, network states, e coordenação descentralizada.
Penalize projetos sem utilidade comunitária clara ou não alinhados com network states."""
    for prop in state['proposals']:
        print(f"   -> Avaliando: {prop.proposal_id}")
        msgs = [
            SystemMessage(content=SYSTEM_BASE + papel_community),
            HumanMessage(content=f"Proposta para avaliação comunitária:\n{prop.proposal_text}\nIntenção/MVP: {prop.intent}\nGitHub URL: {prop.github_url}")
        ]
        res = llm.with_structured_output(EvaluationResult).invoke(msgs)
        prop.community_score = res.score
        prop.community_feedback = res.feedback
        updated_proposals.append(prop)
        events.append({"sender": "Embaixador Comunitário", "message": f"Nota para {prop.proposal_id}: {res.score}. Feedback: {res.feedback}", "type": "chat"})
    return {"proposals": updated_proposals, "events": events}

def node_finance_batch(state: BatchState) -> dict:
    events = [{"sender": "Analista Financeiro", "message": f"Auditando viabilidade financeira e sustentabilidade de {len(state['proposals'])} propostas...", "type": "info"}]
    updated_proposals = []
    papel_finance = """
Seu Papel: Analista Financeiro do Cofre do Ipê Village (Torneio).
Avalie a eficiência do uso do grant de $2.500 USD:
- O escopo é entregouável em 8 dias de pop-up?
- Há modelo de sustentabilidade pós-grant (taxa, token, revenue share on-chain)?
- O custo de infra on-chain (gas, oracles, hardware) foi calculado?
- Risco alto de não entrega?
Penalize projetos com escopo irrealista para 8 dias ou sem modelo econômico claro."""
    for prop in state['proposals']:
        print(f"   -> Avaliando: {prop.proposal_id}")
        msgs = [
            SystemMessage(content=SYSTEM_BASE + papel_finance),
            HumanMessage(content=f"Proposta para avaliação pessoal:\n{prop.proposal_text}\nIntenção/MVP: {prop.intent}\nGitHub URL: {prop.github_url}")
        ]
        res = llm.with_structured_output(EvaluationResult).invoke(msgs)
        prop.finance_score = res.score
        prop.finance_feedback = res.feedback
        updated_proposals.append(prop)
        events.append({"sender": "Analista Financeiro", "message": f"Nota para {prop.proposal_id}: {res.score}. Feedback: {res.feedback}", "type": "chat"})
    return {"proposals": updated_proposals, "events": events}

def node_competition_judge(state: BatchState) -> dict:
    print("\n[JUIZ DE COMPETIÇÃO] Decidindo o Vencedor...")
    
    summary_list = []
    for p in state['proposals']:
        summary_list.append({
            "id": p.proposal_id,
            "avg_score": p.average_score,
            "auditor": f"{p.auditor_score}: {p.auditor_feedback}",
            "community": f"{p.community_score}: {p.community_feedback}",
            "finance": f"{p.finance_score}: {p.finance_feedback}"
        })

    prompt = f"""Você é o Juiz Supremo do Torneio de Grants do Ipê Village 2026.
    Sua missão é escolher UM vencedor único entre as propostas abaixo, priorizando:
    1. Alinhamento com os valores do Ipê: descentralização, privacidade, integração físico-digital.
    2. Impacto real e imediato nos residentes do Village ou Veritas Village.
    3. Entregouável concreto em até 8 dias de pop-up.
    4. Sustentabilidade financeira pós-grant.

    REJEITE automaticamente projetos Web2 puros ou ferramentas corporativas centralizadas.

    PROPOSTAS DISPUTANDO:
    {json.dumps(summary_list, indent=2, ensure_ascii=False)}

    Retorne ESTRITAMENTE um JSON:
    {{
        "winner_id": "<ID da proposta vencedora>",
        "reasoning": "<Justificativa detalhada formatada em Markdown. Use um resumo inicial, subtítulos (###), bullet points e frases curtas para UI limpa.>"
    }}
    """
    
    res = judge_llm.with_structured_output(CompetitionDecision).invoke(prompt)
    
    winner = next((p for p in state['proposals'] if p.proposal_id == res.winner_id), None)
    
    if not winner:
        events = [{"sender": "Juiz de Competição", "message": f"PROPOSTA REJEITADA. MOTIVO:\n{res.reasoning}", "type": "chat"}]
        return {
            "winner": None,
            "final_reasoning": res.reasoning,
            "events": events
        }
    
    # Adiciona a tabela com os scores do vencedor no final
    table_html = f'''
    <br><table class="eval-table">
        <tr><th>Critério / Avaliador</th><th>Nota da Proposta Vencedora (Passe o mouse)</th></tr>
        <tr>
            <td>Auditor Técnico</td>
            <td><div class="tooltip-container">{winner.auditor_score}<span class="tooltip-text">{winner.auditor_feedback}</span></div></td>
        </tr>
        <tr>
            <td>Embaixador Comunitário</td>
            <td><div class="tooltip-container">{winner.community_score}<span class="tooltip-text">{winner.community_feedback}</span></div></td>
        </tr>
        <tr>
            <td>Analista Financeiro</td>
            <td><div class="tooltip-container">{winner.finance_score}<span class="tooltip-text">{winner.finance_feedback}</span></div></td>
        </tr>
    </table>
    '''
    res.reasoning += table_html
    
    # Prints removed to avoid UnicodeEncodeError in Windows terminal
    
    events = [{"sender": "Juiz de Competição", "message": f"VENCEDOR ESCOLHIDO: {winner.proposal_id}. MOTIVO: {res.reasoning}", "type": "chat"}]
    
    return {
        "winner": winner,
        "final_reasoning": res.reasoning,
        "events": events
    }


# --------------------------
# 6. Grafo de Competição
# --------------------------
workflow = StateGraph(BatchState)

workflow.add_node("auditor", node_auditor_batch)
workflow.add_node("community", node_community_batch)
workflow.add_node("finance", node_finance_batch)
workflow.add_node("judge", node_competition_judge)

# Fluxo Linear de Competição (mas agentes podem rodar em paralelo se configurado)
workflow.add_edge(START, "auditor")
workflow.add_edge("auditor", "community")
workflow.add_edge("community", "finance")
workflow.add_edge("finance", "judge")
workflow.add_edge("judge", END)

app = workflow.compile()

# ----------
# Teste de Competição
# ----------
if __name__ == "__main__":
    test_proposals = [
        Proposal(
            proposal_id="PROG_001_EDU",
            proposal_text="EduMesh: Rede P2P para escolas rurais usando hardware reciclado. Baixo custo, alto impacto social.",
            recipient_wallet_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            grant_amount=500
        ),
        Proposal(
            proposal_id="PROG_002_FIN",
            proposal_text="IpePay: Gateway de pagamentos para comerciantes locais com taxa zero. Foco em adoção cripto.",
            recipient_wallet_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            grant_amount=1500
        ),
        Proposal(
            proposal_id="PROG_003_SEC",
            proposal_text="CyberGuard: Sistema de monitoramento de segurança para a rede da cidade detectando ataques Sybil.",
            recipient_wallet_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            grant_amount=800
        )
    ]
    
    print("--- INICIANDO TORNEIO DE GOVERNANCA - IPE CITY ---")
    print("-" * 50)
    
    final_output = app.invoke({"proposals": test_proposals})
    
    print("\n" + "="*50)
    print("--- RESULTADO DO TORNEIO ---")
    print(f"Vencedor: {final_output['winner'].proposal_id}")
    print(f"Motivo: {final_output['final_reasoning']}")
    print(f"Transação: {final_output['tx_hash']}")
    print("="*50)
