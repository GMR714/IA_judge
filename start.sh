#!/bin/bash

# Inicia o servidor Python (FastAPI)
# O Railway injeta a porta automaticamente na variável de ambiente $PORT
echo "Iniciando servidor FastAPI na porta ${PORT:-8888}..."
python server.py
