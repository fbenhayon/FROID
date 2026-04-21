# FROID v3.0 — Entrega 4B: Plano Unificado Definitivo
## Pipelines de Análise (froid-voice + froid-face)
## Fusão: API Facial (4 partes) + API Voice + Plano 4B Original

---

## FASE 1: froid-voice (Porta 3002)
### Arquivos:
```
packages/froid-voice/
├── requirements.txt
├── Dockerfile
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI + WebSocket
│   ├── config.py                   # Constantes, thresholds, referências
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # REST endpoints (health, session results)
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── pipeline.py             # VAD + openSMILE (da API Voice)
│   │   ├── normalizer.py           # Baseline 60s + Sexo + EMA (da API Voice)
│   │   ├── clinical_mapper.py      # Scoring clínico (da API Voice)
│   │   ├── prosody_analyzer.py     # F0, Jitter, Shimmer, HNR (Parselmouth)
│   │   ├── spectral_analyzer.py    # 7 Bandas Espectrais (do Plano 4B)
│   │   ├── zonal_analyzer.py       # 12 Zonas FROID (do Plano 4B)
│   │   ├── subharmonic_analyzer.py # Sub-harmônicos 5-20 Hz (do Plano 4B)
│   │   └── speech_rate_analyzer.py # Taxa de fala (librosa)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── voice_packet.py         # ZonalEnergyPacket + ClinicalScores
│   │   └── voice_config.py         # SessionConfig (sex, calibration)
│   ├── colorimetry/
│   │   ├── __init__.py
│   │   └── color_mapper.py         # 7 níveis (do Plano 4B)
│   └── utils/
│       ├── __init__.py
│       └── audio_buffer.py         # Buffer circular
└── tests/
    └── test_voice_integration.py
```

## FASE 2: froid-face (Porta 3003)
### Arquivos:
```
packages/froid-face/
├── requirements.txt
├── Dockerfile
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI + WebSocket
│   ├── config.py                   # Thresholds clínicos ajustáveis
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # REST endpoints
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── landmark_extractor.py   # MediaPipe 468pts (da API Facial Parte 4)
│   │   ├── action_unit_classifier.py # FACS → AUs (da API Facial)
│   │   ├── temporal_hmm.py         # HMM 4 estados + Viterbi (da API Facial Parte 4)
│   │   ├── emotion_classifier.py   # 7 emoções (combinações de AUs)
│   │   ├── asymmetry_analyzer.py   # D-face/S-face (da API Facial Parte 4)
│   │   ├── microexpression_detector.py
│   │   └── capture_quality.py      # Qualidade de captura (da API Facial)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── facial_packet.py        # FacialEmotionPacket
│   │   └── clinical_flag.py        # ClinicalFlag
│   ├── facs/
│   │   ├── __init__.py
│   │   ├── au_definitions.py       # 46 AUs mapeadas
│   │   └── emotion_au_mapping.py   # Emoção → AUs
│   └── utils/
│       ├── __init__.py
│       └── frame_buffer.py
└── tests/
    └── test_face_integration.py
```

## FASE 3: Protobuf + Integração
- proto/froid_stream.proto (schema unificado)
- Integração com identity-vault (SessionOrchestrator)
- Redis Pub/Sub entre serviços

## FASE 4: Testes de Aceitação
- test-e4b.js (20+ cenários)
- cleanup-e4b.js + seed-e4b.js
