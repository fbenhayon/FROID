FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/packages/froid-face

COPY packages/froid-face/requirements.txt ./

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY packages/froid-face/ ./

EXPOSE 3003

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3003"]
