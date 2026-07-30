FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Usuário não-privilegiado (UID fixo 10001) — o processo não roda como root.
# O volume ./data no host precisa pertencer a este UID (ver comandos do Hetzner).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser
USER 10001
# Worker único é intencional: o estado de sessão (motor de tick + ingestão de
# voz/face) é mantido em memória no processo. A concorrência vem de mover a DSP
# para thread pool (asyncio.to_thread), não de múltiplos workers — que exigiriam
# store de sessão compartilhado antes de serem seguros.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
