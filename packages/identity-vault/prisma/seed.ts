import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

async function main() {
  console.log('Seed iniciado...');
  
  const hashedPassword = await bcrypt.hash('FroidAdmin2026!', 10);
  
  const user = await prisma.user.create({
    data: {
      email: 'fabio.admin@froid.com',
      password: hashedPassword,
      name: 'Fabio Benhayon',
      role: 'admin',
    },
  });
  
  await prisma.professional.create({
    data: {
      userId: user.id,
      name: 'Fabio Benhayon',
      crp: 'CRP-06/123456',
      specialty: 'Psicologia Clinica',
    },
  });
  
  await prisma.subscription.create({
    data: {
      userId: user.id,
      planType: 'unlimited_monthly',
      status: 'active',
      creditsTotal: 999999,
      creditsRemaining: 999999,
      amount: 0,
      paymentMethod: 'dev_account',
      expiryDate: new Date('2027-12-31'),
    },
  });
  
  console.log('Seed OK!');
}

main().catch(console.error).finally(() => prisma.$disconnect());
