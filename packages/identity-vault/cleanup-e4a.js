/**
 * FROID v3.0 - Entrega 4A
 * Cleanup: Remove dados de sessão para testes limpos
 */
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  console.log('=== FROID E4A - Cleanup ===\n');

  // 1. Remover SessionConsentSnapshots
  const snapshots = await prisma.sessionConsentSnapshot.deleteMany({});
  console.log(`  [DELETED] SessionConsentSnapshot: ${snapshots.count}`);

  // 2. Remover HashChainBlocks de eventos de sessão
  const chainBlocks = await prisma.hashChainBlock.deleteMany({
    where: {
      eventType: { in: ['SESSION_STARTED', 'SESSION_BLOCKED', 'SESSION_ENDED'] },
    },
  });
  console.log(`  [DELETED] HashChainBlock (session events): ${chainBlocks.count}`);

  // 3. Remover LegalEvents de sessão
  const legalEvents = await prisma.legalEvent.deleteMany({
    where: {
      eventType: { in: ['SESSION_STARTED', 'SESSION_BLOCKED', 'SESSION_ENDED'] },
    },
  });
  console.log(`  [DELETED] LegalEvent (session events): ${legalEvents.count}`);

  // 4. Remover Sessions
  const sessions = await prisma.session.deleteMany({});
  console.log(`  [DELETED] Session: ${sessions.count}`);

  // 5. Remover ConsentRecords de teste (apenas os criados pelo seed-e4a)
  const consents = await prisma.consentRecord.deleteMany({
    where: {
      patientId: { startsWith: 'e4a-' },
    },
  });
  console.log(`  [DELETED] ConsentRecord (e4a-*): ${consents.count}`);

  // 6. Remover Professionals de teste
  const professionals = await prisma.professional.deleteMany({
    where: {
      id: { startsWith: 'e4a-' },
    },
  });
  console.log(`  [DELETED] Professional (e4a-*): ${professionals.count}`);

  // 7. Remover Patients de teste
  const patients = await prisma.patient.deleteMany({
    where: {
      id: { startsWith: 'e4a-' },
    },
  });
  console.log(`  [DELETED] Patient (e4a-*): ${patients.count}`);

  // 8. Remover LegalText system_policy (criado pelo seed-e4a)
  try {
    await prisma.legalText.delete({
      where: { legalTextId: 'system_policy' },
    });
    console.log('  [DELETED] LegalText: system_policy');
  } catch (e) {
    console.log('  [SKIP] LegalText system_policy não encontrado');
  }

  console.log('\n=== Cleanup concluído ===');
}

main()
  .catch((e) => {
    console.error('Erro no cleanup:', e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
