import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding test data for E2B...');

  const patientId = '66367355-6677-4488-9999-568393847585';
  const professionalId = '98854322-8765-4321-bbbb-cccdddeeefff';

  await prisma.patients.upsert({
    where: { id: patientId },
    update: {},
    create: {
      id: patientId,
      fullName: 'Test Patient E2B',
      cpf: '12345678901',
      email: 'patient@test.com',
      dateOfBirth: new Date('1990-01-01'),
      gender: 'M',
      region: 'SP'
    }
  });

  // Limpar consentimentos antigos para garantir um estado limpo para os testes
  await prisma.consent_records.deleteMany({
    where: { patientId }
  });
  console.log('Existing consents wiped for test patient.');

  await prisma.professionals.upsert({
    where: { id: professionalId },
    update: {},
    create: {
      id: professionalId,
      fullName: 'Test Professional E2B',
      cpf: '98765432101',
      email: 'pro@test.com',
      registrationNumber: 'CRM123',
      registrationType: 'CRM'
    }
  });

  console.log('Test data seeded (Patient and Professional).');
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
