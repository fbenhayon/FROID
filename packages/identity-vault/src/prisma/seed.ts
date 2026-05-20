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

  const hashedMaster = await bcrypt.hash('froid_master_2024', 10);
  const hashedPassword = await bcrypt.hash('froid123', 10);

  // Administrador master — único com permissão de alterar o sistema
  const masterUser = await prisma.users.create({
    data: {
      email: 'fbenhayon@froid.com.br',
      password: hashedMaster,
      role: 'superadmin',
    },
  });

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

  console.log('✅ Usuários criados:', {
    master: masterUser.email,
    admin: adminUser.email,
    test: testUser.email,
  });

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
    },
  });

  await prisma.professionals.create({
    data: {
      userId: testUser.id,
      name: 'Dra. Maria Santos',
      crp: 'CRP-02/67890',
      specialty: 'Neuropsicologia',
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

  await prisma.patients.create({
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

  await prisma.clinic_prompts.create({
    data: {
      title: 'Análise Vocal Emocional',
      category: 'voice',
      promptText: 'Analise o tom emocional da voz considerando: frequência fundamental, prosódia, taxa de fala e energia espectral. Identifique sinais de depressão, ansiedade ou mania.',
      isActive: true,
      createdBy: professional1.id,
    },
  });

  await prisma.clinic_prompts.create({
    data: {
      title: 'Análise de Micro-expressões Faciais',
      category: 'face',
      promptText: 'Analise as micro-expressões faciais usando FACS (Facial Action Coding System). Identifique Action Units relacionadas a emoções genuínas vs. mascaradas.',
      isActive: true,
      createdBy: professional1.id,
    },
  });

  await prisma.clinic_prompts.create({
    data: {
      title: 'Análise de Fusão Multimodal',
      category: 'fusion',
      promptText: 'Integre dados de voz e face para detectar incongruências emocionais. Calcule score de congruência e identifique possíveis dissociações afetivas.',
      isActive: true,
      createdBy: professional1.id,
    },
  });

  console.log('✅ Prompts clínicos criados');

  // ============================================================================
  // 6. CRIAR SESSÃO DE EXEMPLO
  // ============================================================================
  console.log('📅 Criando sessão de exemplo...');

  await prisma.sessions.create({
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

  console.log('✅ Sessão criada');

  // ============================================================================
  // RESUMO
  // ============================================================================
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║   🌱 SEED CONCLUÍDO COM SUCESSO! 🌱       ║');
  console.log('╚════════════════════════════════════════════╝');
  console.log('');
  console.log('📊 Dados criados:');
  console.log('  - 3 usuários (1 superadmin + 2 profissionais)');
  console.log('  - 2 profissionais');
  console.log('  - 2 pacientes');
  console.log('  - 3 prompts clínicos');
  console.log('  - 1 sessão de exemplo');
  console.log('');
  console.log('🔐 Credenciais:');
  console.log('  [MASTER]  fbenhayon@froid.com.br  /  froid_master_2024');
  console.log('  [DEMO]    admin@froid.com          /  froid123');
  console.log('  [DEMO]    test@froid.com           /  froid123');
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
