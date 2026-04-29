import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import os
from competitive_engine import app as langgraph_app, Proposal
from graph_engine import app as graph_app

app = FastAPI()

# Configuração de Template e arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

class TournamentRequest(BaseModel):
    proposals: List[dict]

@app.get("/")
async def get_index():
    return FileResponse("index.html")

@app.post("/run-tournament")
async def run_tournament(request: TournamentRequest):
    # Converte os dicts em objetos Proposal
    proposals = [Proposal(**p) for p in request.proposals]
    
    async def event_generator():
        # Inicializa o estado
        state = {"proposals": proposals, "events": []}
        
        # Executa o LangGraph em modo stream
        # Nota: Usamos sync_to_async ou rodamos direto se o LangGraph suportar astream
        try:
            # Iteramos pelos 'updates' do grafo
            for output in langgraph_app.stream(state, stream_mode="updates"):
                # Captura os eventos adicionados por cada nó
                for node_name, data in output.items():
                    if "events" in data:
                        for event in data["events"]:
                            # Formata como Server-Sent Event
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.8) # Pequena pausa para efeito de 'digitação'
            
            yield "data: {\"type\": \"done\"}\n\n"
        except Exception as e:
            error_event = {"sender": "Sistema", "message": f"Erro crítico: {str(e)}", "type": "error"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/run-graph")
async def run_graph(request: TournamentRequest):
    # Pega apenas a primeira proposta enviada para o modo singular
    prop = request.proposals[0]
    
    async def event_generator():
        state = {
            "proposal_id": prop.get("proposal_id", "PROG_000_TEST"),
            "proposal_text": prop.get("proposal_text", "..."),
            "github_url": prop.get("github_url", ""),
            "intent": prop.get("intent", ""),
            "recipient_wallet_address": prop.get("recipient_wallet_address", "0x00000"),
            "grant_amount": prop.get("grant_amount", 0),
            "iteration_count": 0,
            "debate_history": [],
            "events": []
        }
        
        try:
            for output in graph_app.stream(state, stream_mode="updates"):
                for node_name, data in output.items():
                    if "events" in data:
                        for event in data["events"]:
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.8)
            
            yield "data: {\"type\": \"done\"}\n\n"
        except Exception as e:
            error_event = {"sender": "Sistema", "message": f"Erro crítico: {str(e)}", "type": "error"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/contract-config")
async def get_contract_config():
    return FileResponse("contract_config.json", media_type="application/json")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8888))
    uvicorn.run(app, host="0.0.0.0", port=port)
