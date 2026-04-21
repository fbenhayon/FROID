/**
 * FROID v3.0 - Entrega 4B
 * Teste de Integração: froid-voice + froid-face
 * 
 * Pré-requisitos:
 * - identity-vault rodando na porta 3001
 * - froid-voice rodando na porta 3002
 * - froid-face rodando na porta 3003
 * - Seed e4a executado (pacientes e sessões de teste)
 */
const http = require('http');

const VOICE_URL = 'http://localhost:3002';
const FACE_URL = 'http://localhost:3003';
const VAULT_URL = 'http://localhost:3001/api';

let passed = 0;
let failed = 0;
let total = 0;

function request(baseUrl, method, path) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, baseUrl);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function assert(condition, message) {
  total++;
  if (condition) {
    passed++;
    console.log(`  [PASS] #${total} ${message}`);
  } else {
    failed++;
    console.log(`  [FAIL] #${total} ${message}`);
  }
}

async function testVoiceHealth() {
  console.log('\n--- Grupo 1: froid-voice Health ---');
  
  const res = await request(VOICE_URL, 'GET', '/api/voice/health');
  assert(res.status === 200, 'Voice health returns 200');
  assert(res.body.service === 'froid-voice', 'Service name is froid-voice');
  assert(res.body.status === 'healthy', 'Status is healthy');
  assert(res.body.capabilities && res.body.capabilities.opensmile_egemaps === true, 'Has openSMILE capability');
  assert(res.body.capabilities && res.body.capabilities.froid_12_zones === true, 'Has 12 Zones capability');
  assert(res.body.capabilities && res.body.capabilities.spectral_7_bands === true, 'Has 7 Bands capability');
  assert(res.body.capabilities && res.body.capabilities.clinical_scoring === true, 'Has clinical scoring');
}

async function testVoiceConfig() {
  console.log('\n--- Grupo 2: froid-voice Config ---');
  
  const res = await request(VOICE_URL, 'GET', '/api/voice/config');
  assert(res.status === 200, 'Voice config returns 200');
  assert(Array.isArray(res.body.zones) && res.body.zones.length === 12, 'Has 12 FROID zones');
  assert(Array.isArray(res.body.spectral_bands) && res.body.spectral_bands.length === 7, 'Has 7 spectral bands');
  assert(res.body.color_map && Object.keys(res.body.color_map).length === 7, 'Has 7 color levels');
  assert(res.body.calibration_duration_sec === 60, 'Calibration is 60 seconds');
}

async function testFaceHealth() {
  console.log('\n--- Grupo 3: froid-face Health ---');
  
  const res = await request(FACE_URL, 'GET', '/api/face/health');
  assert(res.status === 200, 'Face health returns 200');
  assert(res.body.service === 'froid-face', 'Service name is froid-face');
  assert(res.body.status === 'healthy', 'Status is healthy');
  assert(res.body.capabilities && res.body.capabilities.mediapipe_468pts === true, 'Has MediaPipe 468pts');
  assert(res.body.capabilities && res.body.capabilities.hmm_temporal === true, 'Has HMM temporal');
  assert(res.body.capabilities && res.body.capabilities.d_face_s_face === true, 'Has D-face/S-face');
  assert(res.body.capabilities && res.body.capabilities.microexpression_detection === true, 'Has microexpression detection');
  assert(res.body.capabilities && res.body.capabilities.genuineness_score === true, 'Has genuineness score');
}

async function testIdentityVaultIntegration() {
  console.log('\n--- Grupo 4: Identity Vault Integration ---');
  
  const res = await request(VAULT_URL, 'GET', '/sessions/patient/e4a-patient-001');
  assert(res.status === 200, 'Can query sessions from identity-vault');
  assert(Array.isArray(res.body), 'Returns array of sessions');
}

async function testVoiceSessionNotFound() {
  console.log('\n--- Grupo 5: Voice Session Validation ---');
  
  const res = await request(VOICE_URL, 'GET', '/api/voice/session/non-existent');
  assert(res.status === 404, 'Voice returns 404 for non-existent session');
}

async function testFaceSessionNotFound() {
  console.log('\n--- Grupo 6: Face Session Validation ---');
  
  const res = await request(FACE_URL, 'GET', '/api/face/session/non-existent');
  assert(res.status === 404, 'Face returns 404 for non-existent session');
}

async function run() {
  console.log('=== FROID E4B - Teste de Integração ===');
  console.log(`Voice: ${VOICE_URL}`);
  console.log(`Face:  ${FACE_URL}`);
  console.log(`Vault: ${VAULT_URL}\n`);

  try {
    await testVoiceHealth();
    await testVoiceConfig();
    await testFaceHealth();
    await testIdentityVaultIntegration();
    await testVoiceSessionNotFound();
    await testFaceSessionNotFound();
  } catch (err) {
    console.error('\n[ERRO]:', err.message);
    console.log('Verifique se todos os serviços estão rodando.');
  }

  console.log('\n=== Resultado Final ===');
  console.log(`  Total:    ${total}`);
  console.log(`  Passed:   ${passed}`);
  console.log(`  Failed:   ${failed}`);
  console.log(`  Taxa:     ${((passed / total) * 100).toFixed(1)}%`);

  if (failed === 0) {
    console.log('\n>>> TODOS OS TESTES PASSARAM! <<<');
  } else {
    console.log(`\n>>> ${failed} teste(s) falharam. <<<`);
    process.exit(1);
  }
}

run();
