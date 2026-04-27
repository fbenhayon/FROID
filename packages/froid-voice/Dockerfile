FROM python:3.11-bookworm

# Instala ferramentas de compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Define workdir para a pasta do serviço
WORKDIR /app/packages/froid-voice

# Copia requirements do caminho correto (contexto raiz)
COPY packages/froid-voice/requirements.txt ./

# Instala dependências
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia o código fonte
COPY packages/froid-voice/ ./

EXPOSE 3002

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3002"]
