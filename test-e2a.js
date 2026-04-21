const fetch = require('node-fetch'); // Ensure fetch points to global or similar 
// Will just use built-in fetch on Node 18+

const API = 'http://localhost:3001/api';

async function logResult(name, promise) {
  try {
    const res = await promise;
    if (res.ok) {
      console.log(`✅ PASS: ${name}`);
      return await res.json();
    } else {
      console.error(`❌ FAIL: ${name} (Status: ${res.status}) - ${await res.text()}`);
      return null;
    }
  } catch (e) {
    console.error(`❌ FAIL: ${name} (Error: ${e.message})`);
    return null;
  }
}

async function runTests() {
  console.log("=== INICIANDO TESTES ENTREGA 2A ===");
  
  // 1. Create Patient
  console.log("Criando paciente MOCK para testes...");
  const randCpf = Math.floor(Math.random() * 100000000000).toString().padStart(11, '0');
  const patientRes = await fetch(`${API}/patients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fullName: 'Tester 2A',
      cpf: randCpf,
      email: `test-${randCpf}@froid.com`,
      dateOfBirth: '1990-01-01T00:00:00.000Z',
      gender: 'O',
      region: 'SP'
    })
  });
  
  const patient = await patientRes.json();
  if (!patient.id) {
    console.error("FALHA AO CRIAR PACIENTE", patient);
    return;
  }
  const pid = patient.id;

  // 8.1 Concessao
  let grant1 = await logResult('1-7: POST /consents/grant (audio_recording)', fetch(`${API}/consents/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'audio_recording', purpose: 'teste_base', collectionContext: 'signup' })
  }));

  let failDup = await logResult('8: Bloqueio Mesmos Escopos (409 Conflict)', fetch(`${API}/consents/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'audio_recording', purpose: 'teste_base', collectionContext: 'signup' })
  }).then(r => r.status === 409 ? { ok: true, json: ()=>{} } : { ok: false, status: r.status, text: ()=>r.text() }));

  let failInvScope = await logResult('9: Escopo invalido (400 Bad Request)', fetch(`${API}/consents/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'invalid_scope', purpose: 'teste_base', collectionContext: 'signup' })
  }).then(r => r.status === 400 ? { ok: true, json: ()=>{} } : { ok: false, status: r.status, text: ()=>r.text() }));

  let failPid = await logResult('10: PatientId inexistente (404)', fetch(`${API}/consents/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: '00000000-0000-0000-0000-000000000000', scope: 'video_recording', purpose: 'teste_base', collectionContext: 'signup' })
  }).then(r => r.status === 404 ? { ok: true, json: ()=>{} } : { ok: false, status: r.status, text: ()=>r.text() }));

  // 8.2 Negacao
  let deny1 = await logResult('11-13: POST /consents/deny', fetch(`${API}/consents/deny`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'voice_analysis', purpose: 'teste_nega', collectionContext: 'signup' })
  }));

  // 8.3 Revogacao
  let revoke1 = await logResult('14-17: POST /consents/revoke', fetch(`${API}/consents/revoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'audio_recording' })
  }));

  let failRevokeNA = await logResult('18: Revocar o que nao esta ativo (404)', fetch(`${API}/consents/revoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'audio_recording' })
  }).then(r => r.status === 404 ? { ok: true, json: ()=>{} } : { ok: false, status: r.status, text: ()=>r.text() }));

  let grantRegrant = await logResult('19: Re-conceder o que foi revogado', fetch(`${API}/consents/grant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scope: 'audio_recording', purpose: 'regrant', collectionContext: 'signup' })
  }));

  // 8.4-8.5 Consultas
  let cActive = await logResult('20-24: GET active scopes', fetch(`${API}/consents/active/${pid}`));
  let cHist = await logResult('25-27: GET history', fetch(`${API}/consents/history/${pid}`));

  // 8.6 Bulks
  let bulk1 = await logResult('28-31: POST grant-bulk', fetch(`${API}/consents/grant-bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patientId: pid, scopes: ['video_recording', 'transcription'], purpose: 'bulk', collectionContext: 'signup' })
  }));

  // 8.7 Full Flow verification
  console.log("=== VERICACAO DE FLUXO E HASHES ===");
  const hist = await fetch(`${API}/consents/history/${pid}`).then(r=>r.json());
  console.log(`Total Historico Eventos: ${hist.length}`);
  // Check uniquely mapped Hashes
  const hashes = new Set(hist.map(h => h.hash));
  if (hashes.size === hist.length) {
    console.log(`✅ PASS: Cada registro tem hash único.`);
  } else {
    console.log(`❌ FAIL: Colisao de Hashes encontrados!`);
  }
}

runTests();
