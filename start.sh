#!/bin/bash

# Garante que a API key esteja exportada para o processo do Ollama
if [ -n "$OLLAMA_API_KEY" ]; then
  export OLLAMA_API_KEY
  echo "OLLAMA_API_KEY detectada. Autenticação cloud habilitada."
else
  echo "⚠️ AVISO: OLLAMA_API_KEY não definida. Modelos cloud não funcionarão."
fi

# Inicia o Ollama em background
echo "Iniciando Ollama..."
ollama serve &

# Aguarda o Ollama estar pronto
echo "Aguardando Ollama iniciar..."
until curl -s http://localhost:11434/api/tags > /dev/null; do
  sleep 2
done

# Baixa o modelo Cloud (isso é rápido pois não baixa pesos pesados)
echo "Baixando modelo cloud: minimax-m2.7:cloud..."
ollama pull minimax-m2.7:cloud

if [ $? -ne 0 ]; then
  echo "❌ ERRO: Falha ao baixar modelo cloud. Verifique OLLAMA_API_KEY."
fi

# Inicia o servidor Python (FastAPI)
# O Railway injeta a porta automaticamente na variável de ambiente $PORT
echo "Iniciando servidor FastAPI na porta ${PORT:-8888}..."
python server.py
