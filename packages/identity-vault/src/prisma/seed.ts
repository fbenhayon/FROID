import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Iniciando seed do banco de dados...');

  // ============================================================================
  // 1. LIMPAR DADOS EXISTENTES (apenas em dev)
  // ============================================================================
  console.log('🧹 Limpando dados antigos...');
  await prisma.clinic_prompts.deleteMany();
  await prisma.sessions.deleteMany();
  await prisma.patients.deleteMany();
  await prisma.professionals.deleteMany();
  await prisma.users.deleteMany();

  // ============================================================================
  // 2. CRIAR USUÁRIOS
  // ============================================================================
  console.log('👤 Criando usuários...');

  const hashedPassword = await bcrypt.hash('froid123', 10);

  const adminUser = await prisma.users.create({
    data: {
      email: 'admin@froid.com',
      password: hashedPassword,
      role: 'professional',
    },
  });

  const testUser = await prisma.users.create({
    data: {
      email: 'test@froid.com',
      password: hashedPassword,
      role: 'professional',
    },
  });

  console.log('✅ Usuários criados:', { adminUser: adminUser.email, testUser: testUser.email });

  // ============================================================================
  // 3. CRIAR PROFISSIONAIS
  // ============================================================================
  console.log('👨‍⚕️ Criando profissionais...');

  const professional1 = await prisma.professionals.create({
    data: {
      userId: adminUser.id,
      name: 'Dr. João Silva',
      crp: 'CRP-01/12345',
      specialty: 'Psicologia Clínica',
      phone: '(11) 98765-4321',
    },
  });

  const professional2 = await prisma.professionals.create({
    data: {
      userId: testUser.id,
      name: 'Dra. Maria Santos',
      crp: 'CRP-02/67890',
      specialty: 'Neuropsicologia',
      phone: '(21) 99876-5432',
    },
  });

  console.log('✅ Profissionais criados');

  // ============================================================================
  // 4. CRIAR PACIENTES
  // ============================================================================
  console.log('👥 Criando pacientes...');

  const patient1 = await prisma.patients.create({
    data: {
      professionalId: professional1.id,
      name: 'Pedro Oliveira',
      cpf: '123.456.789-00',
      birthDate: new Date('1990-05-15'),
      phone: '(11) 91234-5678',
      email: 'pedro@example.com',
    },
  });

  const patient2 = await prisma.patients.create({
    data: {
      professionalId: professional1.id,
      name: 'Ana Costa',
      cpf: '987.654.321-00',
      birthDate: new Date('1985-08-20'),
      phone: '(11) 98765-4321',
      email: 'ana@example.com',
    },
  });

  console.log('✅ Pacientes criados');

  // ============================================================================
  // 5. CRIAR PROMPTS CLÍNICOS
  // ============================================================================
  console.log('💬 Criando prompts clínicos...');

  const voicePrompt1 = await prisma.clinic_prompts.create({
    data: {
      title: 'Análise de Tom Emocional',
      category: 'voice',
      promptText:
        'Analise o tom emocional da voz considerando: frequência fundamental, prosódia, taxa de fala e energia espectral. Identifique sinais de depressão, ansiedade ou mania.',
      isActive: true,
      version: '1.0',
      createdBy: professional1.id,
    },
  });

  const facePrompt1 = await prisma.clinic_prompts.create({
    data: {
      title: 'Análise de Expressões Faciais',
      category: 'face',
      promptText:
        'Analise as micro-expressões faciais usando FACS (Facial Action Coding System). Identifique Action Units relacionadas a emoções genuínas vs. mascaradas.',
      isActive: true,
      version: '1.0',
      createdBy: professional1.id,
    },
  });

  const fusionPrompt1 = await prisma.clinic_prompts.create({
    data: {
      title: 'Análise Multimodal Integrada',
      category: 'fusion',
      promptText:
        'Integre dados de voz e face para detectar incongruências emocionais. Calcule score de congruência e identifique possíveis dissociações afetivas.',
      isActive: true,
      version: '1.0',
      createdBy: professional1.id,
    },
  });

  console.log('✅ Prompts clínicos criados');

  // ============================================================================
  // 6. CRIAR SESSÕES DE EXEMPLO
  // ============================================================================
  console.log('📅 Criando sessões...');

  const session1 = await prisma.sessions.create({
    data: {
      patientId: patient1.id,
      professionalId: professional1.id,
      status: 'completed',
      scheduledFor: new Date('2026-05-10T14:00:00'),
      startedAt: new Date('2026-05-10T14:05:00'),
      endedAt: new Date('2026-05-10T14:55:00'),
      notes: 'Sessão inicial. Paciente apresentou sinais de ansiedade leve.',
    },
  });

  console.log('✅ Sessões criadas');

  // ============================================================================
  // RESUMO
  // ============================================================================
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║   🌱 SEED CONCLUÍDO COM SUCESSO! 🌱       ║');
  console.log('╚════════════════════════════════════════════╝');
  console.log('');
  console.log('📊 Dados criados:');
  console.log(`  - ${2} usuários`);
  console.log(`  - ${2} profissionais`);
  console.log(`  - ${2} pacientes`);
  console.log(`  - ${3} prompts clínicos`);
  console.log(`  - ${1} sessão`);
  console.log('');
  console.log('🔐 Credenciais de teste:');
  console.log('  Email: admin@froid.com');
  console.log('  Senha: froid123');
  console.log('');
}

main()
  .catch((e) => {
    console.error('❌ Erro no seed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
