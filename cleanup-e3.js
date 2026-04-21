const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  console.log('Cleaning up database for a fresh Entrega 3 test...');
  
  // Order matters for foreign keys
  await prisma.hashChainBlock.deleteMany({});
  await prisma.legalEvent.deleteMany({});
  await prisma.consentRecord.deleteMany({});
  await prisma.session.deleteMany({});
  
  console.log('Cleanup complete.');
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
