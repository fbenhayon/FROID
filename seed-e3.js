const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  console.log('Seeding data for Entrega 3 validation...');

  const scopes = [
    { id: 'tcle_audio', scope: 'audio_recording' },
    { id: 'tcle_video', scope: 'video_recording' },
    { id: 'system_policy', scope: 'internal_audit' }
  ];
  
  for (const item of scopes) {
    await prisma.legalText.upsert({
      where: { legalTextId: item.id },
      update: {},
      create: {
        legalTextId: item.id,
        title: item.id === 'system_policy' ? 'Politica de Auditoria' : `Termo de Uso - ${item.scope}`,
        type: item.id === 'system_policy' ? 'policy' : 'consent',
        audience: item.id === 'system_policy' ? 'system' : 'patient',
        context: item.id === 'system_policy' ? 'privacy_center' : 'pre_session',
        shortText: item.id === 'system_policy' ? 'Auditoria de Sistema' : `Autorizo ${item.scope}`,
        expandedText: item.id === 'system_policy' ? 'Texto legal para trilha de auditoria automatica.' : `Este e o termo de uso completo para ${item.scope}.`,
        version: '1.0.0',
        legalBasis: [{ chapter: 'I', article: '7', paragraph: 'I', tag: 'consent' }],
        uiComponent: item.id === 'system_policy' ? 'InternalComponent' : 'ConsentCheckbox',
        enforcementRuleId: 'rule_default',
      }
    });
    console.log(`PASS: LegalText ${item.id} ensured.`);
  }

  // Ensure a professional exists
  await prisma.professional.upsert({
    where: { cpf: '00011122233' },
    update: {},
    create: {
      fullName: 'Dr. Audit E3',
      cpf: '00011122233',
      email: 'audit@froid.com',
      registrationNumber: 'CRM-E3',
      registrationType: 'CRM'
    }
  });

  console.log('Seeding complete.');
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
