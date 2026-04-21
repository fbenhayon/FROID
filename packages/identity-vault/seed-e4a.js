/**
 * FROID v3.0 - Entrega 4A
 * Seed: Prepara dados de teste para Session Orchestrator
 * 
 * Cria:
 * - 1 LegalText system_policy (para eventos de sessão)
 * - 2 Patients (um com consents completos, um sem consents)
 * - 1 Professional
 * - ConsentRecords para Patient 1 (audio, video, voice, transcription, ai_report)
 * - ConsentRecords revogado para Patient 3
 */
const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');
const prisma = new PrismaClient();

function computeHash(data) {
  return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
}

async function main() {
  console.log('=== FROID E4A - Seed ===\n');

  // 1. Criar LegalText system_policy
  const systemPolicy = await prisma.legalText.upsert({
    where: { legalTextId: 'system_policy' },
    update: {},
    create: {
      legalTextId: 'system_policy',
      title: 'Política de Sistema - Eventos de Sessão',
      type: 'policy',
      audience: 'professional',
      context: 'pre_session',
      shortText: 'Política de sistema para auditoria de eventos de sessão.',
      expandedText: '[AGUARDANDO REDAÇÃO JURÍDICA]',
      version: '1.0.0',
      isBlocking: false,
      requiresAction: false,
      requiresSignature: false,
      showCitationInline: false,
      showCitationDetails: true,
      legalBasis: [
        { chapter: 'LGPD', article: '6', paragraph: 'VII', tag: 'seguranca' },
        { chapter: 'LGPD', article: '46', paragraph: null, tag: 'medidas_seguranca' },
      ],
      uiComponent: 'SystemPolicyBadge',
      enforcementRuleId: 'rule_system_policy_v1',
    },
  });
  console.log('  [OK] LegalText: system_policy');

  // 2. Criar Patient 1 - Com consentimentos completos
  const patient1 = await prisma.patient.upsert({
    where: { id: 'e4a-patient-001' },
    update: {},
    create: {
      id: 'e4a-patient-001',
      fullName: 'Ana Silva Santos',
      cpf: '11111111101',
      email: 'ana.e4a@test.com',
      phone: '11999990001',
      dateOfBirth: new Date('1990-05-15'),
      gender: 'F',
      region: 'sudeste',
    },
  });
  console.log(`  [OK] Patient 1: ${patient1.id} (${patient1.fullName})`);

  // 3. Criar Patient 2 - Sem consentimentos (nenhum dado)
  const patient2 = await prisma.patient.upsert({
    where: { id: 'e4a-patient-002' },
    update: {},
    create: {
      id: 'e4a-patient-002',
      fullName: 'Bruno Costa',
      cpf: '22222222202',
      email: 'bruno.e4a@test.com',
      phone: '11999990002',
      dateOfBirth: new Date('1985-08-22'),
      gender: 'M',
      region: 'sudeste',
    },
  });
  console.log(`  [OK] Patient 2: ${patient2.id} (${patient2.fullName})`);

  // 4. Criar Patient 3 - Com consentimento REVOGADO
  const patient3 = await prisma.patient.upsert({
    where: { id: 'e4a-patient-003' },
    update: {},
    create: {
      id: 'e4a-patient-003',
      fullName: 'Carla Mendes',
      cpf: '33333333303',
      email: 'carla.e4a@test.com',
      phone: '11999990003',
      dateOfBirth: new Date('1992-01-10'),
      gender: 'F',
      region: 'sudeste',
    },
  });
  console.log(`  [OK] Patient 3: ${patient3.id} (${patient3.fullName})`);

  // 5. Criar Professional
  const professional = await prisma.professional.upsert({
    where: { id: 'e4a-prof-001' },
    update: {},
    create: {
      id: 'e4a-prof-001',
      fullName: 'Dr. Ricardo Oliveira',
      cpf: '99999999901',
      email: 'ricardo.e4a@test.com',
      registrationNumber: 'CRP-06/123456',
      registrationType: 'CRP',
      specialty: 'Psicologia Clínica',
    },
  });
  console.log(`  [OK] Professional: ${professional.id} (${professional.fullName})`);

  // 6. Criar Consents para Patient 1 (5 escopos granted)
  const scopesToGrant = [
    { scope: 'audio_recording', legalTextId: 'tcle_audio' },
    { scope: 'video_recording', legalTextId: 'tcle_video' },
    { scope: 'voice_analysis', legalTextId: 'tcle_voice' },
    { scope: 'transcription', legalTextId: 'tcle_transcript' },
    { scope: 'ai_report', legalTextId: 'tcle_ai_report' },
  ];

  for (const { scope, legalTextId } of scopesToGrant) {
    const payload = {
      patientId: patient1.id,
      professionalId: null,
      sessionId: null,
      scope,
      purpose: `Autorização para ${scope} - teste E4A`,
      status: 'granted',
      legalTextId,
      legalTextVersion: '1.0.0',
      collectionContext: 'signup',
      ipAddress: '127.0.0.1',
      userAgent: 'seed-e4a',
      geoLocation: null,
      blockchainTxId: null,
      legalBasisSnapshot: [],
      processingPurpose: `Autorização para ${scope}`,
      dataOrigin: 'user_input',
      processingType: 'collection',
      createdBy: patient1.id,
    };
    const hash = computeHash(payload);

    await prisma.consentRecord.create({
      data: { ...payload, hash, legalBasisSnapshot: [] },
    });
    console.log(`  [OK] Consent granted: ${scope} for ${patient1.id}`);
  }

  // 7. Criar Consent REVOGADO para Patient 3
  const revokedPayload = {
    patientId: patient3.id,
    professionalId: null,
    sessionId: null,
    scope: 'audio_recording',
    purpose: 'Autorização para audio - depois revogada',
    status: 'revoked',
    legalTextId: 'tcle_audio',
    legalTextVersion: '1.0.0',
    collectionContext: 'signup',
    ipAddress: '127.0.0.1',
    userAgent: 'seed-e4a',
    geoLocation: null,
    blockchainTxId: null,
    legalBasisSnapshot: [],
    processingPurpose: 'Autorização para audio_recording',
    dataOrigin: 'user_input',
    processingType: 'collection',
    createdBy: patient3.id,
    revokedAt: new Date(),
  };
  const revokedHash = computeHash(revokedPayload);
  await prisma.consentRecord.create({
    data: { ...revokedPayload, hash: revokedHash, legalBasisSnapshot: [] },
  });
  console.log(`  [OK] Consent revoked: audio_recording for ${patient3.id}`);

  // 8. Criar Consent DENIED para Patient 2 (facial_analysis negado)
  const deniedPayload = {
    patientId: patient2.id,
    professionalId: null,
    sessionId: null,
    scope: 'facial_analysis',
    purpose: 'Recusa explícita - teste E4A',
    status: 'denied',
    legalTextId: 'tcle_facial',
    legalTextVersion: '1.0.0',
    collectionContext: 'signup',
    ipAddress: '127.0.0.1',
    userAgent: 'seed-e4a',
    geoLocation: null,
    blockchainTxId: null,
    legalBasisSnapshot: [],
    processingPurpose: 'Recusa explícita',
    dataOrigin: 'user_input',
    processingType: 'collection',
    createdBy: patient2.id,
  };
  const deniedHash = computeHash(deniedPayload);
  await prisma.consentRecord.create({
    data: { ...deniedPayload, hash: deniedHash, legalBasisSnapshot: [] },
  });
  console.log(`  [OK] Consent denied: facial_analysis for ${patient2.id}`);

  console.log('\n=== Resumo do Seed ===');
  console.log('  LegalText system_policy: 1');
  console.log('  Patients: 3 (e4a-patient-001, e4a-patient-002, e4a-patient-003)');
  console.log('  Professional: 1 (e4a-prof-001)');
  console.log('  Consents granted (Patient 1): 5');
  console.log('  Consents revoked (Patient 3): 1');
  console.log('  Consents denied (Patient 2): 1');
  console.log('\n=== Seed concluído ===');
}

main()
  .catch((e) => {
    console.error('Erro no seed:', e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
