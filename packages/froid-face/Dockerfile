FROM python:3.11-bookworm
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    --trusted-host pypi.org \
    --retries 10 \
    --default-timeout 100 \
    -r requirements.txt
COPY . .
EXPOSE 3003
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3003"]

