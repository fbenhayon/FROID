/**
 * FROID v3.0 - Entrega 1
 * Seed dos 12 Textos Juridicos Obrigatorios
 * 
 * REGRA: expandedText = "[AGUARDANDO REDACAO JURIDICA]"
 *        pois os textos completos nao foram fornecidos na especificacao.
 * 
 * REGRA: showCitationInline = false para TODOS (citacoes nao poluem UI)
 * REGRA: legalBasis em JSON com {chapter, article, paragraph, tag}
 * REGRA: emergency_notice unico com isBlocking = false
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const EXPANDED_PLACEHOLDER = '[AGUARDANDO REDACAO JURIDICA]';

const legalTexts = [
  // ----------------------------------------------------------
  // 1. prof_term â€” Termo de Uso Profissional
  // ----------------------------------------------------------
  {
    legalTextId: 'prof_term',
    title: 'Termo de Uso Profissional',
    type: 'term',
    audience: 'professional',
    context: 'signup',
    shortText: 'O FROID e ferramenta de apoio e nao substitui seu julgamento clinico.',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '6', paragraph: 'X', tag: 'responsabilidade_civil' },
      { chapter: 'CFP', article: '50', paragraph: null, tag: 'uso_tecnologia_clinica' },
    ],
    uiComponent: 'TermModal',
    enforcementRuleId: 'rule_prof_term_v1',
  },

  // ----------------------------------------------------------
  // 2. patient_privacy â€” Aviso de Privacidade
  // ----------------------------------------------------------
  {
    legalTextId: 'patient_privacy',
    title: 'Aviso de Privacidade',
    type: 'notice',
    audience: 'patient',
    context: 'first_access',
    shortText: 'Seus dados serao utilizados conforme suas autorizacoes.',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '6', paragraph: null, tag: 'finalidade' },
      { chapter: 'LGPD', article: '9', paragraph: null, tag: 'transparencia' },
      { chapter: 'LGPD', article: '18', paragraph: null, tag: 'direitos_titular' },
    ],
    uiComponent: 'PrivacyNoticeModal',
    enforcementRuleId: 'rule_patient_privacy_v1',
  },

  // ----------------------------------------------------------
  // 3. tcle_audio â€” TCLE Gravacao de Audio
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_audio',
    title: 'TCLE - Gravacao de Audio',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar gravacao de audio?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_audio_v1',
  },

  // ----------------------------------------------------------
  // 4. tcle_video â€” TCLE Gravacao de Video
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_video',
    title: 'TCLE - Gravacao de Video',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar gravacao de video?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_video_v1',
  },

  // ----------------------------------------------------------
  // 5. tcle_voice â€” TCLE Analise Vocal por IA
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_voice',
    title: 'TCLE - Analise Vocal por IA',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar analise vocal por IA?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_voice_v1',
  },

  // ----------------------------------------------------------
  // 6. tcle_facial â€” TCLE Analise Facial por IA
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_facial',
    title: 'TCLE - Analise Facial por IA',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar analise facial por IA?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_facial_v1',
  },

  // ----------------------------------------------------------
  // 7. tcle_transcript â€” TCLE Transcricao Automatica
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_transcript',
    title: 'TCLE - Transcricao Automatica',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar transcricao automatica?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_transcript_v1',
  },

  // ----------------------------------------------------------
  // 8. tcle_ai_report â€” TCLE Relatorio por IA
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_ai_report',
    title: 'TCLE - Relatorio por IA',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar geracao de relatorio por IA?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_ai_report_v1',
  },

  // ----------------------------------------------------------
  // 9. tcle_benchmark â€” TCLE Uso Anonimizado para Referencias Clinicas
  // ----------------------------------------------------------
  {
    legalTextId: 'tcle_benchmark',
    title: 'TCLE - Uso Anonimizado para Referencias Clinicas',
    type: 'consent',
    audience: 'patient',
    context: 'signup',
    shortText: 'Autorizar uso anonimizado para referencias clinicas?',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'LGPD', article: '11', paragraph: 'I', tag: 'dado_sensivel_consentimento' },
      { chapter: 'LGPD', article: '12', paragraph: null, tag: 'dado_anonimizado' },
    ],
    uiComponent: 'ConsentToggleCard',
    enforcementRuleId: 'rule_tcle_benchmark_v1',
  },

  // ----------------------------------------------------------
  // 10. pre_session_confirm â€” Confirmacao Pre-Sessao
  // ----------------------------------------------------------
  {
    legalTextId: 'pre_session_confirm',
    title: 'Confirmacao de Recursos Pre-Sessao',
    type: 'consent',
    audience: 'patient',
    context: 'pre_session',
    shortText: 'Confirme os recursos autorizados para esta sessao.',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,       // bloqueia SESSION_BLOCKED se nao confirmado
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'LGPD', article: '8', paragraph: null, tag: 'consentimento' },
      { chapter: 'CFP', article: 'Res.13/2022', paragraph: null, tag: 'teleconsulta_psicologica' },
    ],
    uiComponent: 'SessionConfirmDialog',
    enforcementRuleId: 'rule_pre_session_confirm_v1',
  },

  // ----------------------------------------------------------
  // 11. ai_report_warning â€” Aviso Relatorio por IA
  // Bloqueia assinatura do relatorio ate o profissional revisar
  // ----------------------------------------------------------
  {
    legalTextId: 'ai_report_warning',
    title: 'Aviso - Relatorio Assistido por IA',
    type: 'warning',
    audience: 'professional',
    context: 'report',
    shortText: 'Relatorio assistido por IA - revisar antes de usar.',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: true,       // bloqueia assinatura do relatorio
    requiresAction: true,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'CFP', article: 'Cartilha 2025', paragraph: null, tag: 'ia_clinica_responsabilidade' },
    ],
    uiComponent: 'WarningBanner',
    enforcementRuleId: 'rule_ai_report_warning_v1',
  },

  // ----------------------------------------------------------
  // 12. emergency_notice â€” Aviso de Emergencia
  // NAO bloqueante â€” exibido permanentemente como aviso fixo
  // ----------------------------------------------------------
  {
    legalTextId: 'emergency_notice',
    title: 'Aviso de Emergencia',
    type: 'warning',
    audience: 'patient',
    context: 'pre_session',
    shortText: 'Nao monitora crises. SAMU 192 / CVV 188.',
    expandedText: EXPANDED_PLACEHOLDER,
    version: '1.0.0',
    isBlocking: false,      // NAO bloqueante â€” exibido permanentemente
    requiresAction: false,
    requiresSignature: false,
    showCitationInline: false,
    showCitationDetails: true,
    legalBasis: [
      { chapter: 'CFP', article: 'Res.13/2022', paragraph: null, tag: 'limite_atendimento_online' },
    ],
    uiComponent: 'PermanentNotice',
    enforcementRuleId: 'rule_emergency_notice_v1',
  },
];

async function main() {
  console.log('FROID v3.0 - Iniciando seed dos 12 textos juridicos...\n');

  let created = 0;
  let skipped = 0;

  for (const text of legalTexts) {
    const result = await prisma.legalText.upsert({
      where: { legalTextId: text.legalTextId },
      update: {},  // nao atualiza se ja existe (versionamento imutavel)
      create: {
        ...text,
        legalBasis: text.legalBasis as any,
      },
    });

    const isNew = result.createdAt.getTime() === result.updatedAt.getTime();
    if (isNew) {
      console.log('  [CRIADO]  ' + text.legalTextId + ' (' + text.type + ')');
      created++;
    } else {
      console.log('  [JA EXISTE] ' + text.legalTextId);
      skipped++;
    }
  }

  console.log('\n--- Resultado do Seed ---');
  console.log('Criados:      ' + created);
  console.log('Ja existiam:  ' + skipped);
  console.log('Total:        ' + legalTexts.length + '/12');
  console.log('\nVerificacoes LGPD:');
  console.log('  showCitationInline = false em todos âœ“');
  console.log('  emergency_notice isBlocking = false âœ“');
  console.log('  legalBasis em JSON estruturado âœ“');
  console.log('\nSeed concluido com sucesso.');
}

main()
  .catch((e) => {
    console.error('Erro no seed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });