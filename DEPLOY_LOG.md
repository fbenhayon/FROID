## [2026-06-01 12:37:06] PATCH V3 — Disco ZYTO, Gráfico DR, AU Descriptions, IA Chat, Vídeo Real
[PATCH V3] froid-data.ts criado com AU dict + zone clinical descriptions
[PATCH V3] GeneralSessionChart.tsx criado (barras horizontais + linha DR)
[PATCH V3] VoiceSpectrumDisc.tsx redesenhado (números fora, centro FROID)
[PATCH V3] AIInsights.tsx refeito (chat bubbles + 10 prompts nativos)
[PATCH V3] MediaStatus.tsx garantido
[PATCH V3] ClinicalNotes.tsx garantido
[PATCH V3] LiveSession.tsx merge final concluído

========================================
PATCH V3 APLICADO COM SUCESSO
========================================
## [2026-06-01 14:16:03] PATCH V4 — Timer 55min, Coherence Line, Video Debug, LLM Ready, Barras Verticais
[PATCH V4] Backend tick alterado para 500ms
[PATCH V4] LiveSession.tsx final: timer 55min, encerrar, coherence line, video debug
[PATCH V4] Import path corrigido

========================================
PATCH V4 CONCLUIDO
========================================
Suba os servidores:
Terminal 1: cd /root/froid-project/froid-server && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Terminal 2: cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
## [2026-06-01 16:00:05] PATCH V5 — Barras ZYTO, AI Proxy, 10s Aggregate, Eixos IPM, Video Diag, Dashboard Pro
[PATCH V5] Backend atualizado com proxy /api/insights
[PATCH V5] VoiceSpectrumDisc.tsx → barras horizontais ZYTO com DR central
[PATCH V5] LiveSession.tsx: buffer 10s, navigate /dashboard, video diag

========================================
PATCH V5 CONCLUIDO
========================================
PASSOS FINAIS OBRIGATORIOS:
1. Reinstalar backend: cd /root/froid-project/froid-server && source venv/bin/activate && pip install -r requirements.txt
2. Subir backend: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
3. Subir frontend: cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso: http://204.168.229.32:5173/#/dashboard
## [2026-06-01 16:23:10] PATCH V6 — Tooltips seguros, Câmera Simulada, Rotas Dashboard, Debug Visual

========================================
PATCH V6 CONCLUIDO
========================================
Reinstalar backend (httpx novo):
  cd /root/froid-project/froid-server && source venv/bin/activate && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso direto (sem camera):
  http://204.168.229.32:5173/#/dashboard
Acesso COM camera (tunel SSH no SEU PC):
  ssh -L 5173:localhost:5173 -L 8000:localhost:8000 root@204.168.229.32
  http://localhost:5173/#/dashboard
## [2026-06-01 16:55:28] PATCH V7 — IPM Grande, Zonas Unificado, IA Proxy Fix, Dissonâncias Tempo Real, Riscos/Subharmônicos Restaurados
[PATCH V7] Backend proxy /api/insights corrigido
[PATCH V7] IPMLineChart grande com baseline tracejado
[PATCH V7] VoiceSpectrumDisc único gráfico de zonas, barras horizontais coloridas
[PATCH V7] AIInsights com debug de erro e proxy backend
[PATCH V7] LiveSession: tempo real, riscos/subharmônicos, IPM grande, sem GeneralSessionChart

========================================
PATCH V7 CONCLUIDO
========================================
Reinstalar backend (httpx):
  cd /root/froid-project/froid-server && source venv/bin/activate && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso:
  http://204.168.229.32:5173/#/dashboard
## [2026-06-01 18:33:32] PATCH V8 — IPM ±10 Baseline, Risco/Subharmonic Charts, Transcrição, NotebookLM Context, Canvas Default
[PATCH V8] Backend com audio_meta, knowledge base, proxy OpenAI

========================================
PATCH V8 CONCLUIDO
========================================
Subir backend:
  cd /root/froid-project/froid-server && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso direto (canvas simulado ativo):
  http://204.168.229.32:5173/#/dashboard
Tunel SSH para camera real (execute no SEU PC):
  ssh -L 5173:localhost:5173 -L 8000:localhost:8000 root@204.168.229.32
## [2026-06-01 20:08:07] PATCH V9 — DR Média 12 Zonas, Barras Coloridas, IPM Dobrado, Compromissos, Transcrição 10min
[PATCH V9] Backend com DR, words/10min, commitments, transcribe endpoint
[PATCH V9] Frontend: DR, IPM dobrado, Riscos, Subharmônicos, Compromissos, Transcrição enriquecida

========================================
PATCH V9 CONCLUIDO
========================================
Subir backend:
  cd /root/froid-project/froid-server && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso:
  http://204.168.229.32:5173/#/dashboard
## [2026-06-02 15:37:24] PATCH V9 — DR Média 12 Zonas, Barras Coloridas, IPM Dobrado, Compromissos, Transcrição 10min
[PATCH V9] Backend com DR, words/10min, commitments, transcribe endpoint
[PATCH V9] Frontend: DR, IPM dobrado, Riscos, Subharmônicos, Compromissos, Transcrição enriquecida

========================================
PATCH V9 CONCLUIDO
========================================
Subir backend:
  cd /root/froid-project/froid-server && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso:
  http://204.168.229.32:5173/#/dashboard
## [2026-06-03 11:59:37] PATCH V10 — Riscos/Emocoes independentes, Mapa bilateral, IPM livre, Compromissos, Tooltips
## [2026-06-03 12:01:47] PATCH V10 — Riscos/Emocoes independentes, Mapa bilateral, IPM livre, Compromissos, Tooltips
## [2026-06-03 12:02:56] PATCH V10 — Riscos/Emocoes independentes, Mapa bilateral, IPM livre, Compromissos, Tooltips
