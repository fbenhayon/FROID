export const SUPPORTED_SESSION_LOCALES = ["pt-BR", "en-US", "fr-FR", "es-ES"] as const;

export type SessionLocale = (typeof SUPPORTED_SESSION_LOCALES)[number];

export type SessionLanguagePreferences = {
  patientUiLocale: SessionLocale;
  spokenLanguage: SessionLocale;
  analysisLanguage: SessionLocale;
  reportLocale: SessionLocale;
};

export const DEFAULT_SESSION_LOCALE: SessionLocale = "pt-BR";
export const SESSION_LANGUAGE_STORAGE_KEY = "froid_session_language_preferences_v1";

export const SESSION_LOCALES: Record<
  SessionLocale,
  { nativeName: string; shortLabel: string; validationStatus: "validated" | "pilot" }
> = {
  "pt-BR": { nativeName: "Português (Brasil)", shortLabel: "PT-BR", validationStatus: "validated" },
  "en-US": { nativeName: "English (United States)", shortLabel: "EN-US", validationStatus: "pilot" },
  "fr-FR": { nativeName: "Français (France)", shortLabel: "FR-FR", validationStatus: "pilot" },
  "es-ES": { nativeName: "Español (España)", shortLabel: "ES-ES", validationStatus: "pilot" },
};

const LOCALE_ALIASES: Record<string, SessionLocale> = {
  pt: "pt-BR",
  "pt-br": "pt-BR",
  en: "en-US",
  "en-us": "en-US",
  fr: "fr-FR",
  "fr-fr": "fr-FR",
  es: "es-ES",
  "es-es": "es-ES",
};

export function normalizeSessionLocale(
  value: unknown,
  fallback: SessionLocale = DEFAULT_SESSION_LOCALE,
): SessionLocale {
  const candidate = String(value || "").trim();
  if ((SUPPORTED_SESSION_LOCALES as readonly string[]).includes(candidate)) {
    return candidate as SessionLocale;
  }
  return LOCALE_ALIASES[candidate.toLowerCase()] || fallback;
}

export function defaultSessionLanguagePreferences(
  locale: SessionLocale = DEFAULT_SESSION_LOCALE,
): SessionLanguagePreferences {
  return {
    patientUiLocale: locale,
    spokenLanguage: locale,
    analysisLanguage: locale,
    reportLocale: locale,
  };
}

export function loadSessionLanguagePreferences(): SessionLanguagePreferences {
  if (typeof window === "undefined") return defaultSessionLanguagePreferences();
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SESSION_LANGUAGE_STORAGE_KEY) || "{}");
    const spokenLanguage = normalizeSessionLocale(parsed.spokenLanguage);
    return {
      patientUiLocale: normalizeSessionLocale(parsed.patientUiLocale, spokenLanguage),
      spokenLanguage,
      analysisLanguage: normalizeSessionLocale(parsed.analysisLanguage, spokenLanguage),
      reportLocale: normalizeSessionLocale(parsed.reportLocale, spokenLanguage),
    };
  } catch {
    return defaultSessionLanguagePreferences();
  }
}

export function saveSessionLanguagePreferences(preferences: SessionLanguagePreferences) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSION_LANGUAGE_STORAGE_KEY, JSON.stringify(preferences));
  document.documentElement.lang = preferences.patientUiLocale;
}

export function sessionLocaleOptions() {
  return SUPPORTED_SESSION_LOCALES.map((locale) => ({
    value: locale,
    label: SESSION_LOCALES[locale].nativeName,
    validationStatus: SESSION_LOCALES[locale].validationStatus,
  }));
}

export function countSpokenUnits(text: string, locale: SessionLocale): number {
  const clean = String(text || "").trim();
  if (!clean) return 0;
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    const Segmenter = (Intl as any).Segmenter;
    const segmenter = new Segmenter(locale, { granularity: "word" });
    return [...segmenter.segment(clean)].filter((part: any) => part.isWordLike).length;
  }
  return clean.split(/\s+/).filter(Boolean).length;
}

const DASHBOARD_TRANSLATIONS: Record<Exclude<SessionLocale, "pt-BR">, Record<string, string>> = {
  "en-US": {
    "Dashboard Profissional": "Professional Dashboard",
    "Dashboard Profissional Resumido": "Professional Summary Dashboard",
    "Dashboard Longitudinal do Paciente": "Longitudinal Patient Dashboard",
    "Paciente": "Patient",
    "Paciente não encontrado": "Patient not found",
    "Voltar ao dashboard": "Back to dashboard",
    "Voltar": "Back",
    "Dashboard resumido": "Summary dashboard",
    "Dashboard detalhado": "Detailed dashboard",
    "Administrativo": "Administration",
    "Sair": "Sign out",
    "Resumo profissional": "Professional summary",
    "Pacientes": "Patients",
    "Devido": "Due",
    "Recebido": "Received",
    "Pendente": "Pending",
    "Carga": "Load",
    "Carga média": "Average load",
    "Comunicação": "Communication",
    "Continuidade": "Continuity",
    "Para revisão": "For review",
    "Meus Pacientes": "My Patients",
    "Últimas sessões, métricas médias e resultado clínico resumido.": "Latest sessions, average metrics, and concise clinical result.",
    "Idioma": "Language",
    "Sessão Remota": "Remote Session",
    "Presencial": "In person",
    "Celular": "Mobile",
    "Ver Detalhes": "View details",
    "Paciente sem nome": "Unnamed patient",
    "Não informado": "Not provided",
    "Ação sugerida": "Suggested action",
    "Qualidade": "Quality",
    "Estado atual": "Current status",
    "Indicadores médios de todas as sessões": "Average indicators across all sessions",
    "Indicadores das últimas 3 sessões": "Indicators from the last 3 sessions",
    "Média": "Average",
    "Ver": "View",
    "Resultado da sessão": "Session result",
    "Meus prompts": "My prompts",
    "Contexto carregado a partir do paciente selecionado.": "Context loaded from the selected patient.",
    "Passe o mouse sobre um paciente para carregar o contexto.": "Hover over a patient to load their context.",
    "Pacientes e indicadores médios": "Patients and average indicators",
    "Sessões": "Sessions",
    "Prioridade": "Priority",
    "Tom": "Tone",
    "Nenhum paciente com relatório disponível.": "No patient report is available.",
    "Histórico de Sessões": "Session history",
    "Resumo do paciente": "Patient summary",
    "Total de Sessões": "Total sessions",
    "Inativas": "Inactive",
    "Ativas": "Active",
    "Análises": "Analyses",
    "Atenção": "Attention",
    "Status definido pelo profissional": "Status set by the professional",
    "Ativo": "Active",
    "Inativo": "Inactive",
    "Painel de acompanhamento": "Follow-up panel",
    "Status": "Status",
    "Estado clínico": "Clinical status",
    "Observações do profissional": "Professional notes",
    "Salvar observação": "Save note",
    "Salvando...": "Saving...",
    "Resumo longitudinal": "Longitudinal summary",
    "Resultado mais recente": "Latest result",
    "Abrir relatório da última sessão": "Open latest session report",
    "Indicadores de seguimento": "Follow-up indicators",
    "Relatório da Consulta": "Session Report",
    "Relatório não encontrado": "Report not found",
    "Sessão": "Session",
    "Duração": "Duration",
    "Linha comparativa da sessão": "Session comparison",
  },
  "fr-FR": {
    "Dashboard Profissional": "Tableau de bord professionnel",
    "Dashboard Profissional Resumido": "Tableau de bord professionnel synthétique",
    "Dashboard Longitudinal do Paciente": "Tableau longitudinal du patient",
    "Paciente": "Patient",
    "Paciente não encontrado": "Patient introuvable",
    "Voltar ao dashboard": "Retour au tableau de bord",
    "Voltar": "Retour",
    "Dashboard resumido": "Tableau synthétique",
    "Dashboard detalhado": "Tableau détaillé",
    "Administrativo": "Administration",
    "Sair": "Se déconnecter",
    "Resumo profissional": "Synthèse professionnelle",
    "Pacientes": "Patients",
    "Devido": "Dû",
    "Recebido": "Reçu",
    "Pendente": "En attente",
    "Carga": "Charge",
    "Carga média": "Charge moyenne",
    "Comunicação": "Communication",
    "Continuidade": "Continuité",
    "Para revisão": "À réviser",
    "Meus Pacientes": "Mes patients",
    "Últimas sessões, métricas médias e resultado clínico resumido.": "Dernières séances, métriques moyennes et résultat clinique synthétique.",
    "Idioma": "Langue",
    "Sessão Remota": "Séance à distance",
    "Presencial": "Présentiel",
    "Celular": "Mobile",
    "Ver Detalhes": "Voir les détails",
    "Paciente sem nome": "Patient sans nom",
    "Não informado": "Non renseigné",
    "Ação sugerida": "Action suggérée",
    "Qualidade": "Qualité",
    "Estado atual": "État actuel",
    "Indicadores médios de todas as sessões": "Indicateurs moyens de toutes les séances",
    "Indicadores das últimas 3 sessões": "Indicateurs des 3 dernières séances",
    "Média": "Moyenne",
    "Ver": "Voir",
    "Resultado da sessão": "Résultat de la séance",
    "Meus prompts": "Mes prompts",
    "Contexto carregado a partir do paciente selecionado.": "Contexte chargé à partir du patient sélectionné.",
    "Passe o mouse sobre um paciente para carregar o contexto.": "Survolez un patient pour charger son contexte.",
    "Pacientes e indicadores médios": "Patients et indicateurs moyens",
    "Sessões": "Séances",
    "Prioridade": "Priorité",
    "Tom": "Ton",
    "Nenhum paciente com relatório disponível.": "Aucun rapport patient disponible.",
    "Histórico de Sessões": "Historique des séances",
    "Resumo do paciente": "Synthèse du patient",
    "Total de Sessões": "Total des séances",
    "Inativas": "Inactives",
    "Ativas": "Actives",
    "Análises": "Analyses",
    "Atenção": "Attention",
    "Status definido pelo profissional": "Statut défini par le professionnel",
    "Ativo": "Actif",
    "Inativo": "Inactif",
    "Painel de acompanhamento": "Tableau de suivi",
    "Status": "Statut",
    "Estado clínico": "État clinique",
    "Observações do profissional": "Notes du professionnel",
    "Salvar observação": "Enregistrer la note",
    "Salvando...": "Enregistrement...",
    "Resumo longitudinal": "Synthèse longitudinale",
    "Resultado mais recente": "Résultat le plus récent",
    "Abrir relatório da última sessão": "Ouvrir le rapport de la dernière séance",
    "Indicadores de seguimento": "Indicateurs de suivi",
    "Relatório da Consulta": "Rapport de séance",
    "Relatório não encontrado": "Rapport introuvable",
    "Sessão": "Séance",
    "Duração": "Durée",
    "Linha comparativa da sessão": "Comparaison de la séance",
  },
  "es-ES": {
    "Dashboard Profissional": "Panel profesional",
    "Dashboard Profissional Resumido": "Panel profesional resumido",
    "Dashboard Longitudinal do Paciente": "Panel longitudinal del paciente",
    "Paciente": "Paciente",
    "Paciente não encontrado": "Paciente no encontrado",
    "Voltar ao dashboard": "Volver al panel",
    "Voltar": "Volver",
    "Dashboard resumido": "Panel resumido",
    "Dashboard detalhado": "Panel detallado",
    "Administrativo": "Administración",
    "Sair": "Cerrar sesión",
    "Resumo profissional": "Resumen profesional",
    "Pacientes": "Pacientes",
    "Devido": "Devengado",
    "Recebido": "Recibido",
    "Pendente": "Pendiente",
    "Carga": "Carga",
    "Carga média": "Carga media",
    "Comunicação": "Comunicación",
    "Continuidade": "Continuidad",
    "Para revisão": "Para revisar",
    "Meus Pacientes": "Mis pacientes",
    "Últimas sessões, métricas médias e resultado clínico resumido.": "Últimas sesiones, métricas medias y resultado clínico resumido.",
    "Idioma": "Idioma",
    "Sessão Remota": "Sesión remota",
    "Presencial": "Presencial",
    "Celular": "Móvil",
    "Ver Detalhes": "Ver detalles",
    "Paciente sem nome": "Paciente sin nombre",
    "Não informado": "No informado",
    "Ação sugerida": "Acción sugerida",
    "Qualidade": "Calidad",
    "Estado atual": "Estado actual",
    "Indicadores médios de todas as sessões": "Indicadores medios de todas las sesiones",
    "Indicadores das últimas 3 sessões": "Indicadores de las últimas 3 sesiones",
    "Média": "Media",
    "Ver": "Ver",
    "Resultado da sessão": "Resultado de la sesión",
    "Meus prompts": "Mis prompts",
    "Contexto carregado a partir do paciente selecionado.": "Contexto cargado a partir del paciente seleccionado.",
    "Passe o mouse sobre um paciente para carregar o contexto.": "Pase el cursor sobre un paciente para cargar su contexto.",
    "Pacientes e indicadores médios": "Pacientes e indicadores medios",
    "Sessões": "Sesiones",
    "Prioridade": "Prioridad",
    "Tom": "Tono",
    "Nenhum paciente com relatório disponível.": "No hay informes de pacientes disponibles.",
    "Histórico de Sessões": "Historial de sesiones",
    "Resumo do paciente": "Resumen del paciente",
    "Total de Sessões": "Total de sesiones",
    "Inativas": "Inactivas",
    "Ativas": "Activas",
    "Análises": "Análisis",
    "Atenção": "Atención",
    "Status definido pelo profissional": "Estado definido por el profesional",
    "Ativo": "Activo",
    "Inativo": "Inactivo",
    "Painel de acompanhamento": "Panel de seguimiento",
    "Status": "Estado",
    "Estado clínico": "Estado clínico",
    "Observações do profissional": "Observaciones del profesional",
    "Salvar observação": "Guardar observación",
    "Salvando...": "Guardando...",
    "Resumo longitudinal": "Resumen longitudinal",
    "Resultado mais recente": "Resultado más reciente",
    "Abrir relatório da última sessão": "Abrir informe de la última sesión",
    "Indicadores de seguimento": "Indicadores de seguimiento",
    "Relatório da Consulta": "Informe de la sesión",
    "Relatório não encontrado": "Informe no encontrado",
    "Sessão": "Sesión",
    "Duração": "Duración",
    "Linha comparativa da sessão": "Comparación de la sesión",
  },
};

export function dashboardText(locale: unknown, portugueseText: string): string {
  const normalized = normalizeSessionLocale(locale);
  if (normalized === "pt-BR") return portugueseText;
  return DASHBOARD_TRANSLATIONS[normalized][portugueseText] || portugueseText;
}

type PatientCopy = {
  loadingInvite: string;
  invalidInvite: string;
  unavailableInvite: string;
  invitationTitle: string;
  invitationSubtitle: string;
  patient: string;
  session: string;
  payment: string;
  confirmed: string;
  confirmedBody: string;
  enterSession: string;
  patientPortal: string;
  patientRoom: string;
  checking: string;
  connected: string;
  blocked: string;
  enableMedia: string;
  enablingMedia: string;
  mediaActive: string;
  mediaPermission: string;
  pilotNotice: string;
  accountLocated: string;
  accountLocatedBody: string;
  accessPassword: string;
  fullName: string;
  document: string;
  email: string;
  confirmEmail: string;
  phone: string;
  birthDate: string;
  portalPassword: string;
  confirmPassword: string;
  privacyAuthorizations: string;
  privacyBody: string;
  consentLabels: Record<string, string>;
  confirming: string;
  confirmPasswordEntry: string;
  confirmRegistration: string;
  packageLabel: (count: number) => string;
  singleSession: string;
  sessionValue: string;
  total: string;
  errors: Record<string, string>;
};

const PATIENT_COPY: Record<SessionLocale, PatientCopy> = {
  "pt-BR": {
    loadingInvite: "Carregando convite FROID...",
    invalidInvite: "Convite inválido.",
    unavailableInvite: "Convite indisponível",
    invitationTitle: "Convite para sessão FROID",
    invitationSubtitle: "Confirme seus dados e autorizações antes da sessão.",
    patient: "Paciente",
    session: "Sessão",
    payment: "Pagamento",
    confirmed: "Convite confirmado",
    confirmedBody: "Seu cadastro e suas autorizações foram registrados. A sessão está liberada.",
    enterSession: "Entrar na sessão",
    patientPortal: "Portal do paciente",
    patientRoom: "Sala do paciente",
    checking: "Validando convite...",
    connected: "Paciente conectado",
    blocked: "Entrada bloqueada",
    enableMedia: "Ativar áudio e vídeo",
    enablingMedia: "Ativando...",
    mediaActive: "Áudio e vídeo ativos",
    mediaPermission: "Câmera e microfone aguardando permissão.",
    pilotNotice: "Idioma internacional em validação controlada.",
    accountLocated: "Cadastro e autorizações localizados",
    accountLocatedBody: "Para liberar esta sessão, informe somente sua senha. Suas autorizações permanecem válidas até que você as altere no Portal do Paciente.",
    accessPassword: "Senha de acesso",
    fullName: "Nome completo",
    document: "CPF ou documento",
    email: "E-mail",
    confirmEmail: "Confirmar e-mail",
    phone: "WhatsApp ou telefone",
    birthDate: "Data de nascimento",
    portalPassword: "Senha de acesso ao portal",
    confirmPassword: "Confirmar senha",
    privacyAuthorizations: "Privacidade e autorizações",
    privacyBody: "O FROID processa dados pessoais e dados sensíveis de saúde, incluindo áudio, vídeo, métricas vocais, transcrição e análises de apoio profissional.",
    consentLabels: {
      terms_of_use: "Li e aceito as condições de utilização do FROID.",
      privacy_policy: "Li e aceito a política de privacidade.",
      sensitive_data_processing: "Autorizo o tratamento de dados sensíveis de saúde para esta sessão.",
      audio_video_processing: "Autorizo a captura e o processamento de áudio, vídeo e métricas vocais.",
      research_anonymized: "Autorizo o uso anonimizado para pesquisa e melhoria do FROID.",
    },
    confirming: "Confirmando...",
    confirmPasswordEntry: "Confirmar senha e entrar",
    confirmRegistration: "Confirmar cadastro e convite",
    packageLabel: (count) => `Pacote com ${count} sessões`,
    singleSession: "Sessão avulsa",
    sessionValue: "Valor da sessão",
    total: "Total",
    errors: {
      document: "Informe o documento do paciente.",
      email: "Informe o e-mail do paciente.",
      emailMatch: "A confirmação de e-mail não confere.",
      passwordLength: "A senha do paciente deve ter no mínimo 8 caracteres.",
      passwordMatch: "A confirmação de senha não confere.",
      confirmation: "Não foi possível confirmar.",
    },
  },
  "en-US": {
    loadingInvite: "Loading FROID invitation...",
    invalidInvite: "Invalid invitation.",
    unavailableInvite: "Invitation unavailable",
    invitationTitle: "Invitation to a FROID session",
    invitationSubtitle: "Confirm your details and authorizations before the session.",
    patient: "Patient",
    session: "Session",
    payment: "Payment",
    confirmed: "Invitation confirmed",
    confirmedBody: "Your registration and authorizations have been recorded. You may now join the session.",
    enterSession: "Join session",
    patientPortal: "Patient portal",
    patientRoom: "Patient room",
    checking: "Validating invitation...",
    connected: "Patient connected",
    blocked: "Entry blocked",
    enableMedia: "Enable audio and video",
    enablingMedia: "Enabling...",
    mediaActive: "Audio and video active",
    mediaPermission: "Camera and microphone are awaiting permission.",
    pilotNotice: "International language available under controlled validation.",
    accountLocated: "Registration and authorizations found",
    accountLocatedBody: "Enter only your password to access this session. Your authorizations remain valid until you change them in the Patient Portal.",
    accessPassword: "Access password",
    fullName: "Full name",
    document: "ID or document",
    email: "Email",
    confirmEmail: "Confirm email",
    phone: "WhatsApp or phone",
    birthDate: "Date of birth",
    portalPassword: "Patient portal password",
    confirmPassword: "Confirm password",
    privacyAuthorizations: "Privacy and authorizations",
    privacyBody: "FROID processes personal and sensitive health information, including audio, video, voice metrics, transcripts, and analyses that support the professional.",
    consentLabels: {
      terms_of_use: "I have read and accept the FROID terms of use.",
      privacy_policy: "I have read and accept the privacy notice.",
      sensitive_data_processing: "I authorize the processing of sensitive health information for this session.",
      audio_video_processing: "I authorize audio, video, and voice-metric capture and processing.",
      research_anonymized: "I authorize anonymized use for research and FROID improvement.",
    },
    confirming: "Confirming...",
    confirmPasswordEntry: "Confirm password and enter",
    confirmRegistration: "Confirm registration and invitation",
    packageLabel: (count) => `${count}-session package`,
    singleSession: "Single session",
    sessionValue: "Session price",
    total: "Total",
    errors: {
      document: "Enter the patient's identification document.",
      email: "Enter the patient's email address.",
      emailMatch: "The email addresses do not match.",
      passwordLength: "The patient password must contain at least 8 characters.",
      passwordMatch: "The passwords do not match.",
      confirmation: "The invitation could not be confirmed.",
    },
  },
  "fr-FR": {
    loadingInvite: "Chargement de l’invitation FROID...",
    invalidInvite: "Invitation non valide.",
    unavailableInvite: "Invitation indisponible",
    invitationTitle: "Invitation à une séance FROID",
    invitationSubtitle: "Confirmez vos informations et autorisations avant la séance.",
    patient: "Patient",
    session: "Séance",
    payment: "Paiement",
    confirmed: "Invitation confirmée",
    confirmedBody: "Votre inscription et vos autorisations ont été enregistrées. Vous pouvez rejoindre la séance.",
    enterSession: "Rejoindre la séance",
    patientPortal: "Portail patient",
    patientRoom: "Salle du patient",
    checking: "Validation de l’invitation...",
    connected: "Patient connecté",
    blocked: "Accès bloqué",
    enableMedia: "Activer l’audio et la vidéo",
    enablingMedia: "Activation...",
    mediaActive: "Audio et vidéo actifs",
    mediaPermission: "La caméra et le microphone attendent votre autorisation.",
    pilotNotice: "Langue internationale disponible en validation contrôlée.",
    accountLocated: "Inscription et autorisations retrouvées",
    accountLocatedBody: "Saisissez uniquement votre mot de passe pour accéder à cette séance. Vos autorisations restent valables jusqu’à leur modification dans le Portail patient.",
    accessPassword: "Mot de passe d’accès",
    fullName: "Nom complet",
    document: "Pièce d’identité ou document",
    email: "E-mail",
    confirmEmail: "Confirmer l’e-mail",
    phone: "WhatsApp ou téléphone",
    birthDate: "Date de naissance",
    portalPassword: "Mot de passe du portail patient",
    confirmPassword: "Confirmer le mot de passe",
    privacyAuthorizations: "Confidentialité et autorisations",
    privacyBody: "FROID traite des données personnelles et des données de santé sensibles, notamment l’audio, la vidéo, les métriques vocales, les transcriptions et les analyses d’aide au professionnel.",
    consentLabels: {
      terms_of_use: "J’ai lu et j’accepte les conditions d’utilisation de FROID.",
      privacy_policy: "J’ai lu et j’accepte la notice de confidentialité.",
      sensitive_data_processing: "J’autorise le traitement de données de santé sensibles pour cette séance.",
      audio_video_processing: "J’autorise la capture et le traitement de l’audio, de la vidéo et des métriques vocales.",
      research_anonymized: "J’autorise l’utilisation anonymisée à des fins de recherche et d’amélioration de FROID.",
    },
    confirming: "Confirmation...",
    confirmPasswordEntry: "Confirmer le mot de passe et accéder",
    confirmRegistration: "Confirmer l’inscription et l’invitation",
    packageLabel: (count) => `Forfait de ${count} séances`,
    singleSession: "Séance individuelle",
    sessionValue: "Prix de la séance",
    total: "Total",
    errors: {
      document: "Saisissez la pièce d’identité du patient.",
      email: "Saisissez l’adresse e-mail du patient.",
      emailMatch: "Les adresses e-mail ne correspondent pas.",
      passwordLength: "Le mot de passe doit comporter au moins 8 caractères.",
      passwordMatch: "Les mots de passe ne correspondent pas.",
      confirmation: "L’invitation n’a pas pu être confirmée.",
    },
  },
  "es-ES": {
    loadingInvite: "Cargando la invitación de FROID...",
    invalidInvite: "Invitación no válida.",
    unavailableInvite: "Invitación no disponible",
    invitationTitle: "Invitación a una sesión FROID",
    invitationSubtitle: "Confirme sus datos y autorizaciones antes de la sesión.",
    patient: "Paciente",
    session: "Sesión",
    payment: "Pago",
    confirmed: "Invitación confirmada",
    confirmedBody: "Su registro y sus autorizaciones se han guardado. Ya puede acceder a la sesión.",
    enterSession: "Entrar en la sesión",
    patientPortal: "Portal del paciente",
    patientRoom: "Sala del paciente",
    checking: "Validando la invitación...",
    connected: "Paciente conectado",
    blocked: "Acceso bloqueado",
    enableMedia: "Activar audio y vídeo",
    enablingMedia: "Activando...",
    mediaActive: "Audio y vídeo activos",
    mediaPermission: "La cámara y el micrófono esperan su autorización.",
    pilotNotice: "Idioma internacional disponible en validación controlada.",
    accountLocated: "Registro y autorizaciones encontrados",
    accountLocatedBody: "Introduzca únicamente su contraseña para acceder a esta sesión. Sus autorizaciones seguirán vigentes hasta que las modifique en el Portal del paciente.",
    accessPassword: "Contraseña de acceso",
    fullName: "Nombre completo",
    document: "Documento de identidad",
    email: "Correo electrónico",
    confirmEmail: "Confirmar correo electrónico",
    phone: "WhatsApp o teléfono",
    birthDate: "Fecha de nacimiento",
    portalPassword: "Contraseña del portal del paciente",
    confirmPassword: "Confirmar contraseña",
    privacyAuthorizations: "Privacidad y autorizaciones",
    privacyBody: "FROID procesa datos personales y datos sensibles de salud, incluidos audio, vídeo, métricas vocales, transcripciones y análisis de apoyo al profesional.",
    consentLabels: {
      terms_of_use: "He leído y acepto las condiciones de uso de FROID.",
      privacy_policy: "He leído y acepto el aviso de privacidad.",
      sensitive_data_processing: "Autorizo el tratamiento de datos sensibles de salud para esta sesión.",
      audio_video_processing: "Autorizo la captura y el procesamiento de audio, vídeo y métricas vocales.",
      research_anonymized: "Autorizo el uso anonimizado para investigación y mejora de FROID.",
    },
    confirming: "Confirmando...",
    confirmPasswordEntry: "Confirmar contraseña y entrar",
    confirmRegistration: "Confirmar registro e invitación",
    packageLabel: (count) => `Paquete de ${count} sesiones`,
    singleSession: "Sesión individual",
    sessionValue: "Precio de la sesión",
    total: "Total",
    errors: {
      document: "Introduzca el documento de identidad del paciente.",
      email: "Introduzca el correo electrónico del paciente.",
      emailMatch: "Los correos electrónicos no coinciden.",
      passwordLength: "La contraseña debe tener al menos 8 caracteres.",
      passwordMatch: "Las contraseñas no coinciden.",
      confirmation: "No se pudo confirmar la invitación.",
    },
  },
};

export function patientCopy(locale: unknown): PatientCopy {
  return PATIENT_COPY[normalizeSessionLocale(locale)];
}
