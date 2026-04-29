# Usa imagem oficial do Python
FROM python:3.10-slim

# Evita que o Python gere arquivos .pyc e permite logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependências do sistema e o binário do Ollama
RUN apt-get update && apt-get install -y \
    curl \
    zstd \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

# Define diretório de trabalho
WORKDIR /app

# Copia requisitos e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Dá permissão de execução ao script de inicialização
RUN chmod +x start.sh

# A porta padrão do FastAPI no seu server.py é 8888, 
# mas o Railway vai sobrescrever isso via variável de ambiente PORT.
EXPOSE 8888
EXPOSE 11434

# Comando para iniciar o container
CMD ["./start.sh"]
