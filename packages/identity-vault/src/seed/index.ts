import { seedLegalTexts } from './legal-texts';

async function main() {
  console.log('🌱 Starting seed...');
  
  await seedLegalTexts();
  
  console.log('✅ Seed completed!');
  process.exit(0);
}

main().catch((e) => {
  console.error('❌ Seed failed:', e);
  process.exit(1);
});
