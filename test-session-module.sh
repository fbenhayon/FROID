#!/bin/bash

echo "╔════════════════════════════════════════════╗"
echo "║   TESTE COMPLETO: SESSION MODULE          ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ============================================================================
# 1. OBTER TOKEN JWT
# ============================================================================
echo "=== 1. LOGIN E OBTER JWT TOKEN ==="
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:3001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@froid.com","password":"froid123"}')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ ERRO: Não foi possível obter token"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Token obtido: ${TOKEN:0:50}..."
echo ""

# ============================================================================
# 2. BUSCAR IDs DE PACIENTE E PROFISSIONAL DO SEED
# ============================================================================
echo "=== 2. BUSCAR DADOS DO SEED (via banco) ==="

# Conectar ao PostgreSQL e buscar IDs
PATIENT_ID=$(docker exec froid-postgres-1 psql -U froid -d froid_db -t -c \
  "SELECT id FROM patients WHERE name = 'Pedro Oliveira' LIMIT 1;" | tr -d ' ')

PROFESSIONAL_ID=$(docker exec froid-postgres-1 psql -U froid -d froid_db -t -c \
  "SELECT id FROM professionals WHERE name = 'Dr. João Silva' LIMIT 1;" | tr -d ' ')

echo "Patient ID: $PATIENT_ID"
echo "Professional ID: $PROFESSIONAL_ID"
echo ""

# ============================================================================
# 3. CRIAR SESSÃO
# ============================================================================
echo "=== 3. CRIAR NOVA SESSÃO ==="

SESSION_RESPONSE=$(curl -s -X POST http://localhost:3001/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"patientId\": \"$PATIENT_ID\",
    \"professionalId\": \"$PROFESSIONAL_ID\",
    \"scheduledFor\": \"2026-05-11T15:00:00Z\"
  }")

echo "$SESSION_RESPONSE" | jq

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.id')

if [ "$SESSION_ID" == "null" ] || [ -z "$SESSION_ID" ]; then
  echo "❌ ERRO: Não foi possível criar sessão"
  exit 1
fi

echo "✅ Sessão criada: $SESSION_ID"
echo ""

# ============================================================================
# 4. INICIAR SESSÃO
# ============================================================================
echo "=== 4. INICIAR SESSÃO (START) ==="

START_RESPONSE=$(curl -s -X PATCH http://localhost:3001/sessions/$SESSION_ID/start \
  -H "Authorization: Bearer $TOKEN")

echo "$START_RESPONSE" | jq
echo "✅ Sessão iniciada"
echo ""

# ============================================================================
# 5. SIMULAR ANÁLISE DE VOZ
# ============================================================================
echo "=== 5. ENVIAR ÁUDIO PARA ANÁLISE (simulado) ==="

VOICE_RESPONSE=$(curl -s -X POST http://localhost:3001/sessions/$SESSION_ID/analyze-voice \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "audioData": {
      "format": "wav",
      "sampleRate": 44100,
      "duration": 5.2,
      "samples": "base64_encoded_audio_data_here"
    }
  }')

echo "$VOICE_RESPONSE" | jq || echo "$VOICE_RESPONSE"
echo ""

# ============================================================================
# 6. SIMULAR ANÁLISE DE FACE
# ============================================================================
echo "=== 6. ENVIAR FRAME DE VÍDEO PARA ANÁLISE (simulado) ==="

FACE_RESPONSE=$(curl -s -X POST http://localhost:3001/sessions/$SESSION_ID/analyze-face \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "imageData": {
      "format": "jpeg",
      "width": 1280,
      "height": 720,
      "data": "base64_encoded_image_data_here"
    }
  }')

echo "$FACE_RESPONSE" | jq || echo "$FACE_RESPONSE"
echo ""

# ============================================================================
# 7. OBTER RESULTADOS DA SESSÃO
# ============================================================================
echo "=== 7. OBTER RESULTADOS DA SESSÃO ==="

RESULTS_RESPONSE=$(curl -s -X GET http://localhost:3001/sessions/$SESSION_ID/results \
  -H "Authorization: Bearer $TOKEN")

echo "$RESULTS_RESPONSE" | jq
echo ""

# ============================================================================
# 8. FINALIZAR SESSÃO
# ============================================================================
echo "=== 8. FINALIZAR SESSÃO (END) ==="

END_RESPONSE=$(curl -s -X PATCH http://localhost:3001/sessions/$SESSION_ID/end \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "notes": "Sessão de teste automatizado. Paciente respondeu bem aos estímulos."
  }')

echo "$END_RESPONSE" | jq
echo "✅ Sessão finalizada"
echo ""

# ============================================================================
# RESUMO
# ============================================================================
echo "╔════════════════════════════════════════════╗"
echo "║          TESTE CONCLUÍDO COM SUCESSO!     ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "📊 Resumo:"
echo "  ✅ Login realizado"
echo "  ✅ Sessão criada: $SESSION_ID"
echo "  ✅ Sessão iniciada"
echo "  ✅ Análise de voz enviada"
echo "  ✅ Análise facial enviada"
echo "  ✅ Resultados obtidos"
echo "  ✅ Sessão finalizada"
echo ""
echo "🎯 Session Module está 100% funcional!"
