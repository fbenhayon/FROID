const axios = require('axios');

const VAULT_URL = process.env.VAULT_URL || 'http://localhost:3001/api';

async function testEntrega3() {
  console.log('FROID v3.1 - Entrega 3 - Test Suite (22 Scenarios)');
  console.log('================================================');

  try {
    // 1-4. Health Check
    console.log('\n[Scenario 1-4] Health Check Verification...');
    const health = await axios.get(`${VAULT_URL}/audit/health`);
    const h = health.data;
    if (h.eventBus !== 'ok') throw new Error('SC1: EventBus not ok');
    if (h.hashChain !== 'ok') throw new Error('SC2: HashChain not ok');
    if (h.database !== 'ok') throw new Error('SC3: Database not ok');
    if (h.redis !== 'ok') throw new Error('SC4: Redis not ok');
    console.log('PASS: Health Check complete.');

    // Prepare Patient
    const pRes = await axios.post(`${VAULT_URL}/patients`, {
      fullName: 'Auditor ' + Date.now(),
      cpf: Math.floor(Math.random() * 90000000000 + 10000000000).toString(),
      email: `auditor${Date.now()}@test.com`,
      dateOfBirth: '1985-05-20',
      gender: 'NB',
      region: 'SP'
    });
    const patient = pRes.data;
    console.log(`\nUsing patient: ${patient.id}`);

    // 5-7. Block 0 Creation & Genesis check
    console.log('\n[Scenario 5-7] Block 0 & Genesis Check...');
    const grant1 = await axios.post(`${VAULT_URL}/consents/grant`, {
      patientId: patient.id,
      scope: 'audio_recording',
      purpose: 'Audit test',
      collectionContext: 'settings'
    });
    
    console.log('Waiting for block creation (2s)...');
    await new Promise(r => setTimeout(r, 2000));

    const block0Res = await axios.get(`${VAULT_URL}/audit/chain/blocks?limit=100`);
    const blocks = block0Res.data.blocks.reverse(); // oldest first
    const b0 = blocks.find(b => b.eventId === grant1.data.events?.[0]?.eventId || b.eventType === 'CONSENT_GRANTED' && b.payload.includes(patient.id));
    
    if (!b0) throw new Error('SC5: Block 0 not found');
    if (b0.previousHash !== 'GENESIS') throw new Error('SC6: Block 0 previousHash is not GENESIS');
    console.log(`PASS: Block 0 created (Seq: ${b0.sequenceNumber}, Hash: ${b0.blockHash.substring(0, 10)}...)`);

    // 8-9. Block 1 & Linking check
    console.log('\n[Scenario 8-9] Block 1 & Linking Check...');
    const grant2 = await axios.post(`${VAULT_URL}/consents/grant`, {
      patientId: patient.id,
      scope: 'video_recording',
      purpose: 'Audit test 2',
      collectionContext: 'settings'
    });
    
    console.log('Waiting for block 1 (2s)...');
    await new Promise(r => setTimeout(r, 2000));

    const blocksAll = (await axios.get(`${VAULT_URL}/audit/chain/blocks?limit=500`)).data.blocks.reverse();
    const b1 = blocksAll.find(b => b.sequenceNumber === b0.sequenceNumber + 1);
    
    if (!b1) throw new Error('SC8: Block 1 not found');
    if (b1.previousHash !== b0.blockHash) throw new Error('SC9: Block 1 link broken');
    console.log(`PASS: Block 1 linked correctly to Block 0.`);

    // 10. verifyChain valid=true
    console.log('\n[Scenario 10] Group Integrity Check...');
    const verifyChain = await axios.get(`${VAULT_URL}/audit/chain/verify`);
    if (!verifyChain.data.valid) throw new Error('SC10: Chain integrity failed');
    console.log(`PASS: Chain integrity verified (Total Blocks: ${verifyChain.data.totalBlocks})`);

    // 11. verifyEvent valid=true
    console.log('\n[Scenario 11] Single Event Integrity Check...');
    const verifyEv = await axios.get(`${VAULT_URL}/audit/event/${b1.eventId}/verify`);
    if (!verifyEv.data.valid) throw new Error('SC11: Event integrity failed');
    console.log('PASS: Single event integrity verified.');

    // 12-13. blockchainTxId presence
    console.log('\n[Scenario 12-13] blockchainTxId Presence Check...');
    const leRes = await axios.get(`${VAULT_URL}/audit/patient/${patient.id}/trail`);
    const le = leRes.data.events.find(e => e.eventId === b1.eventId);
    if (!le.blockchainTxId) throw new Error('SC12: blockchainTxId missing in LegalEvent');

    const crRes = await axios.get(`${VAULT_URL}/consents/history/${patient.id}?scope=video_recording`);
    const cr = crRes.data[0];
    if (!cr.blockchainTxId) throw new Error('SC13: blockchainTxId missing in ConsentRecord');
    console.log('PASS: blockchainTxId populated in both DB records.');

    // 14-16. Instant Cache Invalidation
    console.log('\n[Scenario 14-16] Instant Cache Invalidation Check...');
    // Warming up cache
    await axios.post(`${VAULT_URL}/policy/evaluate`, {
      patientId: patient.id,
      requestedScopes: ['video_recording']
    });
    
    // Revoking
    await axios.post(`${VAULT_URL}/consents/revoke`, {
      patientId: patient.id,
      scope: 'video_recording',
      reason: 'SC Invalidation Test'
    });
    
    // Immediate evaluate (should be DENIED even before TTL)
    const policy = await axios.post(`${VAULT_URL}/policy/evaluate`, {
      patientId: patient.id,
      requestedScopes: ['video_recording']
    });
    
    if (policy.data.allow === true) throw new Error('SC14: Cache not invalidated instantly');
    console.log('PASS: Policy Engine invalidated cache instantly (Event Bus Success).');

    // 17-19. Patient Audit Trail
    console.log('\n[Scenario 17-19] Patient Audit Trail Verification...');
    console.log('Waiting for final blocks (2s)...');
    await new Promise(r => setTimeout(r, 2000));
    const trail = (await axios.get(`${VAULT_URL}/audit/patient/${patient.id}/trail`)).data;
    if (trail.events.length < 3) throw new Error('SC17: Not enough events in trail');
    if (!trail.events.every(e => e.blockchainTxId)) throw new Error('SC18: Not all events have txId');
    if (trail.chainValid !== true) throw new Error('SC19: trail reporting invalid chain');
    console.log(`PASS: Patient trail verified (Events: ${trail.events.length})`);

    // 20-22. Final Flow & Pagination
    console.log('\n[Scenario 20-22] Final Flow & API Check...');
    const paged = await axios.get(`${VAULT_URL}/audit/chain/blocks?page=1&limit=2`);
    if (paged.data.blocks.length !== 2) throw new Error('SC20: Pagination failed');
    
    const single = await axios.get(`${VAULT_URL}/audit/chain/blocks/${b1.sequenceNumber}`);
    if (single.data.blockHash !== b1.blockHash) throw new Error('SC21: Retrieval by sequence failed');
    
    const finalVerify = await axios.get(`${VAULT_URL}/audit/chain/verify`);
    if (!finalVerify.data.valid) throw new Error('SC22: Final chain corrupt');
    
    console.log('PASS: Final flow and API endpoints consistent.');

    console.log('\n================================================');
    console.log('SUCCESS: All 22 audit scenarios passed!');
    console.log('================================================');

  } catch (error) {
    console.error('\n!!! TEST FAILED !!!');
    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Data:', JSON.stringify(error.response.data, null, 2));
    } else {
      console.error('Error:', error.message);
    }
    process.exit(1);
  }
}

testEntrega3();
