const http = require('http');

const IDENTITY_URL = 'http://localhost:3001/api';

async function fetchJson(method, endpoint, body) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(IDENTITY_URL + endpoint);
    const options = {
      method,
      hostname: parsedUrl.hostname,
      port: parsedUrl.port,
      path: parsedUrl.pathname + parsedUrl.search,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, data: json });
        } catch (e) {
          resolve({ status: res.statusCode, data });
        }
      });
    });

    req.on('error', reject);

    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

async function runTests() {
  console.log('--- Inciando Testes FROID Entrega 2B ---');
  let passed = 0;
  let failed = 0;

  function assert(condition, message) {
    if (condition) {
      console.log(`[PASS] ${message}`);
      passed++;
    } else {
      console.error(`[FAIL] ${message}`);
      failed++;
    }
  }

  // 1. OPA Health Check
  const healthRes = await fetchJson('GET', '/policy/health');
  assert(healthRes.status === 200 && healthRes.data.status === 'ok', 'OPA Health check ok');

  const patientId = '66367355-6677-4488-9999-568393847585'; // Valid ID

  // Invalida cache inicio
  await fetchJson('DELETE', `/policy/cache/${patientId}`);

  // Test 1: Sem escopos, deve bloquear
  let res = await fetchJson('POST', '/policy/evaluate', {
    patientId,
    requestedScopes: ['audio_recording', 'ai_report']
  });
  
  assert(res.status === 200 && res.data.allow === false, 'Evaluation blocks when missing consents');
  assert(res.data.blockReason === 'Nenhum escopo valido na intersecao' || res.data.effectiveScopes.length === 0, 'Reason identifies lack of intersection');

  // Test 2: Conceder consents e avaliar novamente
  // Limpar antigos revogando o que houver pra garantir
  // Na vdd vamos apagar ou usar IDs limpos, mas ok dar grant bulk
  const grantBulkBody = {
    patientId,
    professionalId: '98854322-8765-4321-bbbb-cccdddeeefff',
    scopes: ['audio_recording', 'ai_report'],
    purpose: 'Testes de aceitacao E2B',
    collectionContext: 'session'
  };
  await fetchJson('POST', '/consents/grant-bulk', grantBulkBody);

  // Invalida cache de novo pq os consentimentos mudaram (idealmente o ConsentService faria isso)
  await fetchJson('DELETE', `/policy/cache/${patientId}`);

  let resAllow = await fetchJson('POST', '/policy/evaluate', {
    patientId,
    requestedScopes: ['audio_recording', 'ai_report']
  });

  assert(resAllow.data.allow === true, 'Evaluation ALLOWS when consent granted');
  assert(resAllow.data.effectiveScopes.includes('audio_recording') && resAllow.data.effectiveScopes.includes('ai_report'), 'Effective scopes returned');

  // getModules
  let modRes = await fetchJson('GET', `/policy/modules/${patientId}`);
  assert(modRes.data.enabledModules.includes('froid-voice') && modRes.data.enabledModules.includes('froid-nlp'), 'getModules reflects allowed module spaces from data.json');

  // Test 3: Revoke 
  await fetchJson('POST', '/consents/revoke', {
    patientId,
    scope: 'audio_recording',
    reason: 'no longer want'
  });
  await fetchJson('DELETE', `/policy/cache/${patientId}`); // manually invalidate cache
  
  let resRevoked = await fetchJson('POST', '/policy/evaluate', {
    patientId,
    requestedScopes: ['audio_recording', 'ai_report']
  });

  assert(resRevoked.data.allow === false, 'Evaluation BLOCKS if any requested scope is revoked');
  assert(resRevoked.data.blockReason === 'Escopo revogado pelo titular', 'Identified revoked scope reason properly');

  console.log(`\nTests finished. Passed: ${passed}, Failed: ${failed}`);
}

runTests().catch(console.error);
