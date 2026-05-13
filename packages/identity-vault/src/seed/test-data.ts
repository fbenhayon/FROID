import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding test data for E2B...');

  const professionalId = '98854322-8765-4321-bbbb-cccdddeeefff';
  const userId = '11111111-1111-1111-1111-111111111111';
  const patientId = '66367355-6677-4488-9999-568393847585';

  await prisma.users.upsert({
    where: { id: userId },
    update: {},
    create: {
      id: userId,
      email: 'pro@test.com',
      passwordHash: '$2b$10$placeholder',
      role: 'professional',
    }
  });

  await prisma.professionals.upsert({
    where: { id: professionalId },
    update: {},
    create: {
      id: professionalId,
      userId,
      name: 'Test Professional E2B',
      crp: 'CRP-06/123456',
      specialty: 'Clinical Psychology',
    }
  });

  await prisma.patients.upsert({
    where: { id: patientId },
    update: {},
    create: {
      id: patientId,
      professionalId,
      name: 'Test Patient E2B',
      cpf: '12345678901',
      birthDate: new Date('1990-01-01'),
    }
  });

  await prisma.consent_records.deleteMany({
    where: { patientId }
  });
  console.log('Existing consents wiped for test patient.');

  console.log('Test data seeded (User, Professional, Patient).');
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
