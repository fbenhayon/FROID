import { PerceptionZone } from "./froid-engine";
import type { SessionLocale } from "./localization";

export interface ClinicalNote {
  id: string;
  text: string;
  timestamp: number;
}

/** Uma correcao do que o FROID escreveu, na palavra de quem estava la.
 *
 *  Nasceu de um caso real: em 02/09/2026 um paciente leu o relatorio da propria
 *  sessao e apontou quatro erros — uma cidade trocada, uma inferencia afetiva
 *  que ninguem disse, um trecho incoerente e uma palavra faltando. Nenhum era
 *  de indice acustico; todos vieram da transcricao ou do resumo gerado.
 *
 *  `ClinicalNote` nao servia: texto livre, sem alvo, sem autor e sem
 *  precedencia. A correcao ficaria num campo geral, sem apontar o trecho errado,
 *  e quem abrisse o relatorio leria o erro primeiro.
 *
 *  O original nunca e reescrito. Apagar o erro apagaria junto a auditoria e o
 *  par (o que o FROID disse / o que era verdade) — que e o material mais proximo
 *  de um gabarito que existira antes de haver coleta rotulada. */
export type OrigemDaCorrecao = "profissional" | "paciente";

/** Quatro defeitos e uma leitura. A distincao entre eles nao e cosmetica.
 *
 *  DEFEITOS — o sistema errou, e a taxonomia saiu de casos reais, nao de uma
 *  lista imaginada:
 *
 *  - `transcricao_incorreta`: o STT ouviu errado ou deixou cair uma palavra;
 *  - `inferencia_indevida`: o resumo AFIRMOU algo que ninguem disse (o mais
 *    grave dos quatro: e o sistema inventando conteudo);
 *  - `fato_incorreto`: um detalhe factual trocado;
 *  - `trecho_incoerente`: o texto nao faz sentido como esta.
 *
 *  LEITURA — o sistema nao errou:
 *
 *  - `leitura_contestada`: o paciente discorda de uma leitura que ESTAVA
 *    ancorada no que ele disse.
 *
 *  O resumo do corte existe para dizer em poucas palavras a substancia do que
 *  foi tratado, de um jeito que produza um ponto de dissonancia entre paciente
 *  e profissional e traga os dois de volta ao assunto. Quando isso acontece, e
 *  o mecanismo funcionando — material de sessao, nao falha.
 *
 *  Mas dissonancia so tem valor clinico se o paciente NAO puder descarta-la
 *  como defeito. Um erro factual nao e uma versao mais forte de dissonancia:
 *  ele ensina que o relatorio nao e confiavel, e a proxima discordancia
 *  legitima e descartada junto. Fidelidade e pre-condicao da friccao, nao o
 *  oposto dela — e por isso os cinco tipos nao podem viver no mesmo balde. */
export type TipoDeErroNoRelatorio =
  | "transcricao_incorreta"
  | "inferencia_indevida"
  | "fato_incorreto"
  | "trecho_incoerente"
  | "leitura_contestada";

/** A fronteira e factual, nao de gosto: se o trecho AFIRMA algo que nao foi
 *  dito, e defeito; se OFERECE uma leitura do que foi dito, e leitura. */
export function ehDefeitoDoSistema(tipo: TipoDeErroNoRelatorio): boolean {
  return tipo !== "leitura_contestada";
}

export interface CorrecaoDeRelatorio {
  id: string;
  criadoEm: string;
  /** De quem veio o apontamento. Paciente e profissional sao evidencias de
   *  naturezas diferentes, e misturar as duas apagaria o que as torna uteis. */
  origem: OrigemDaCorrecao;
  tipo: TipoDeErroNoRelatorio;
  secao: string;
  corteId?: string;
  /** O texto tal como o FROID produziu. Fica para o erro continuar auditavel. */
  trechoOriginal: string;
  /** O que e correto, na palavra de quem corrigiu. */
  correcao: string;
  observacao?: string;
  /** Quem REGISTROU — pode nao ser de quem veio o apontamento. */
  registradoPor?: string;
}

export interface PatientIdentity {
  id?: string;
  name?: string;
  email?: string;
  phone?: string;
  document?: string;
  sessionMode?: "remote" | "presential" | "presential_mobile";
  captureProfile?: "patient_external_media" | "patient_mobile" | "local_default";
  patientUiLocale?: SessionLocale;
  spokenLanguage?: SessionLocale;
  analysisLanguage?: SessionLocale;
  reportLocale?: SessionLocale;
}

export interface MetricSnapshot {
  label: string;
  startSecond: number;
  endSecond: number;
  sampleCount: number;
  ipmAvg: number;
  idmAvg: number;
  dominantZone: number | null;
  dominantTheme: string;
  coherenceStatus: string;
  emotionalTone: string;
  wordsPerMinute: number;
  theme: string;
  dissonanceCount: number;
  mfcc7: number | null;
  mfcc9: number | null;
  mfcc7Delta?: number | null;
  mfcc9Delta?: number | null;
  mfcc7DeltaDelta?: number | null;
  mfcc9DeltaDelta?: number | null;
  f0Mean: number | null;
  zcr: number | null;
  jitter: number | null;
  shimmer: number | null;
  spectralDelta0_4?: number | null;
  spectralTheta4_8?: number | null;
  spectralAlpha8_12?: number | null;
  spectralBeta12_30?: number | null;
  spectralGamma30_80?: number | null;
  spectralBandIndex?: number | null;
  subharmonic5_12: number | null;
  subharmonic12_20: number | null;
  subharmonic20_40?: number | null;
  vocalBasal85_165?: number | null;
  dnaInfrasoundNuclear?: number | null;
  dnaLimbicModulation?: number | null;
  dnaVocalBasalTension?: number | null;
  dnaAutonomicFlooding?: number | null;
  dnaDissociativeShutdown?: number | null;
  dnaNeurogenicResonance?: number | null;
  dnaSomatoaffectiveDissonance?: number | null;
  dnaSubharmonicIndex?: number | null;
  zones: PerceptionZone[];
}

export interface SessionReportRecord {
  id: string;
  sessionId: string;
  patient?: PatientIdentity;
  patientId?: string;
  patientName?: string;
  patientDocument?: string;
  professionalEmail?: string;
  professional?: {
    email?: string;
    name?: string;
  };
  createdAt: string;
  durationSeconds: number;
  baseline: MetricSnapshot;
  sessionAverage: MetricSnapshot;
  tenMinuteCuts: MetricSnapshot[];
  clinicalNotes: ClinicalNote[];
  /** Ausente em relatorios anteriores a 02/09/2026. */
  correcoes?: CorrecaoDeRelatorio[];
  conversationSummaries: Array<{
    id: string;
    startSecond?: number;
    endSecond?: number;
    startMinute: number;
    endMinute: number;
    theme: string;
    summary: string;
    trigger?: "automatico_10min" | "manual" | "final";
  }>;
  sessionSummary?: {
    theme: string;
    summary: string;
    generatedAt: string;
  };
  froidExplicaConversation?: Array<{ role: string; content: string }>;
  dissonances: Array<{
    id: string;
    timestamp: string;
    elapsedSeconds: number;
    zone: number;
    report: string;
  }>;
  // Dissonâncias evidentes (>= 2 marcadores fora da métrica base ao mesmo tempo).
  evidentDissonances?: Array<{
    id: string;
    timestamp: string;
    elapsedSeconds: number;
    count: number;
    categories: string[];
    markers: Array<{
      key: string;
      label: string;
      category: string;
      value: number;
      band: [number | null, number | null];
      direction: string;
      severity: number;
      unit: string;
      interpretation: string;
    }>;
    summary: string;
    severity?: number;
    isMulti?: boolean;
    peakZone?: number;
    peakZoneTema?: string;
    source: string;
  }>;
  transcript: string;
  transcriptionQuality?: {
    successfulSegments: number;
    emptySegments: number;
    silentSegments: number;
    failedSegments: number;
    undersizedSegments: number;
    latencyP50Ms: number | null;
    latencyP95Ms: number | null;
  };
  spokenLanguage?: SessionLocale;
  analysisLanguage?: SessionLocale;
  reportLocale?: SessionLocale;
  transcriptRetention?: "disabled_summary_only" | "enabled";
  /** Texto redigido pelo profissional, gravado no ato da liberação ao paciente.
   *  Sem isto a cópia que o paciente baixa no portal sairia com a seção
   *  "Anotações do seu profissional" vazia: o texto vive no estado da tela do
   *  profissional, e o portal não tem acesso a ele. */
  patientNotes?: string;
  anonymizedContext?: {
    schemaVersion: string;
    spokenLanguage?: SessionLocale;
    analysisLanguage?: SessionLocale;
    reportLocale?: SessionLocale;
    sessionModality: "remote" | "presential" | "presential_mobile" | "unknown";
    sessionKind: string;
    sessionType?: string;
    treatmentPhase: string;
    sessionOrdinal: number;
    previousSessionsCount?: number;
    intervalSincePreviousDays: number | null;
    sttModel: string;
    llmModel: string;
    algorithmVersion: string;
    metricsVersion?: string;
    weightsVersion?: string;
    audioQuality: string;
    mediaInterruptions: number;
    mediaLossEvents?: number;
    consentAnonymousResearch: boolean;
    privacyTier?: "anonymous_research_datamart";
    piiExcluded?: boolean;
    rawAudioRetained?: boolean;
    literalTranscriptRetained?: boolean;
    deltaIpmFromSessionBaseline?: number | null;
    deltaIdmFromSessionBaseline?: number | null;
    deltaIpmVsLast3?: number | null;
    deltaIdmVsLast3?: number | null;
    deltaIpmVsHistorical?: number | null;
    deltaIdmVsHistorical?: number | null;
    longitudinalTrend?: string;
    emotionalStability?: string;
    recurringThemes?: string[];
    recurringZones?: number[];
    recurringRisks?: string[];
    cuts: Array<{
      cutIndex: number;
      cutTrigger: "automatico_10min" | "manual" | "final";
      startSecond?: number;
      endSecond?: number;
      themePredominant?: string;
      patientSummaryAnon?: string;
      professionalSummaryAnon?: string;
      qualityConfidence: number;
      interventionCategory: string;
      patientResponse: string;
      ipmDeltaFromBaseline?: number | null;
      idmDeltaFromBaseline?: number | null;
      dissonanceDeltaFromBaseline?: number | null;
      ipmDeltaPreviousCut?: number | null;
      idmDeltaPreviousCut?: number | null;
      dissonanceDeltaPreviousCut?: number | null;
      ipmDeltaAfterIntervention?: number | null;
      idmDeltaAfterIntervention?: number | null;
      dissonanceDeltaAfterIntervention?: number | null;
      dominantZoneShift?: string;
      emotionalToneShift?: string;
      cadenceShift?: string;
      semanticCoherenceShift?: string;
      relevantDissonances?: string;
      aggregatedClinicalRisk?: number;
      spectralDelta0_4?: number | null;
      spectralTheta4_8?: number | null;
      spectralAlpha8_12?: number | null;
      spectralBeta12_30?: number | null;
      spectralGamma30_80?: number | null;
      spectralBandIndex?: number | null;
      mfcc7Delta?: number | null;
      mfcc9Delta?: number | null;
      mfcc7DeltaDelta?: number | null;
      mfcc9DeltaDelta?: number | null;
    }>;
  };
  metricsAnalysis?: MetricsAnalysis;
  /** Ausente em relatórios anteriores a 02/09/2026 — ver ProcedenciaDosDados. */
  procedenciaDosDados?: ProcedenciaDosDados;
  metricsAnalysisError?: string;
}

/** De onde vieram os dados que sustentam os índices deste relatório.
 *
 *  Existe por um incidente de 02/09/2026: uma sessão de 24 minutos foi
 *  analisada inteira sobre voz SIMULADA, e o relatório resultante era
 *  indistinguível de um relatório clínico legítimo. Nenhum campo dizia que os
 *  números tinham sido gerados em vez de medidos.
 *
 *  Um documento que não declara a própria base probatória não pode ser lido
 *  com segurança — nem por quem o assina, nem por quem o recebe depois. */
export interface ProcedenciaDosDados {
  /** Total de amostras colhidas na sessão. */
  amostras: number;
  /** Quantas tinham voz REAL do paciente (PCM medido, não gerado). */
  amostrasComVozReal: number;
  /** Quantas tinham leitura facial REAL (blendshapes -> AUs FACS). */
  amostrasComFaceReal: number;
}

export interface MetricsAnalysis {
  schema: string;
  metrics: Array<{
    key: string;
    label: string;
    unit: string;
    category: string;
  }>;
  dashboard: {
    populated_windows: number;
    mean_coverage: number | null;
    mean_confidence: number | null;
    last_dissonance: number | null;
    max_dissonance: number | null;
    data_status: string;
    critical_alerts: number;
    alerts_count: number;
  };
  summary: Record<
    string,
    {
      baseline: number | null;
      baseline_std: number | null;
      session_mean: number | null;
      last: number | null;
      min: number | null;
      max: number | null;
      delta_mean: number | null;
      delta_last: number | null;
      z_last: number | null;
      alerts: string[];
    }
  >;
  evolution: Array<{
    label: string;
    start_min: number;
    end_min: number;
    ipm: number | null;
    idm: number | null;
    words_per_minute: number | null;
    facial_vocal_dissonance: number | null;
    quality: string;
  }>;
  report_rendered: string;
}

const REPORT_STORAGE_KEY = "froid_session_reports_v1";
const SESSION_PATIENT_STORAGE_KEY = "froid_session_patients_v1";
const CURRENT_EMAIL_KEY = "froid_user_email";
const LEGACY_LOCAL_REPORT_OWNER = "fbenhayon@gmail.com";

function normalizeOwnerEmail(email?: string) {
  return String(email || "").trim().toLowerCase();
}

function currentProfessionalEmail() {
  if (typeof window === "undefined") return "";
  return normalizeOwnerEmail(window.localStorage.getItem(CURRENT_EMAIL_KEY) || "");
}

function reportOwnerEmail(report: Partial<SessionReportRecord> & Record<string, any>) {
  return normalizeOwnerEmail(
    report.professionalEmail ||
      report.professional_email ||
      report.professional?.email ||
      "",
  ) || LEGACY_LOCAL_REPORT_OWNER;
}

function reportBelongsToCurrentProfessional(report: Partial<SessionReportRecord> & Record<string, any>) {
  const owner = currentProfessionalEmail();
  return !owner || reportOwnerEmail(report) === owner;
}

export function loadSessionReports(): SessionReportRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(REPORT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed
          .filter((report) => reportBelongsToCurrentProfessional(report))
          .map((report) => hydrateReportPatient(report))
      : [];
  } catch {
    return [];
  }
}

export function saveSessionReport(report: SessionReportRecord) {
  if (typeof window === "undefined") return;
  const owner = currentProfessionalEmail();
  const hydrated = hydrateReportPatient({
    ...report,
    // The complete transcript is archived by the protected backend and is
    // deliberately excluded from persistent browser storage.
    transcript: "",
    professionalEmail: report.professionalEmail || owner,
    professional: {
      ...(report as any).professional,
      email: ((report as any).professional?.email || report.professionalEmail || owner),
    },
  });
  const reports = loadSessionReports();
  const next = [
    hydrated,
    ...reports.filter((item) => item.sessionId !== hydrated.sessionId),
  ].slice(0, 100);
  if (hydrated.sessionId && hydrated.patient) {
    rememberSessionPatient(hydrated.sessionId, hydrated.patient);
  }
  window.localStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(next));
}

export function loadSessionReport(sessionId: string) {
  return loadSessionReports().find((report) => report.sessionId === sessionId);
}

function loadSessionPatients(): Record<string, PatientIdentity> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(SESSION_PATIENT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

export function rememberSessionPatient(sessionId: string, patient: PatientIdentity) {
  if (typeof window === "undefined" || !sessionId) return;
  const current = loadSessionPatients();
  const previous = current[sessionId] || {};
  current[sessionId] = {
    ...previous,
    ...patient,
  };
  window.localStorage.setItem(SESSION_PATIENT_STORAGE_KEY, JSON.stringify(current));
}

export function loadSessionPatient(sessionId: string): PatientIdentity | null {
  if (!sessionId) return null;
  return loadSessionPatients()[sessionId] || null;
}

export function getReportPatient(report: SessionReportRecord): PatientIdentity {
  const stored = loadSessionPatient(report.sessionId) || {};
  return {
    ...stored,
    ...(report.patient || {}),
    id: report.patient?.id || report.patientId || stored.id,
    name: report.patient?.name || report.patientName || stored.name || "Paciente sem nome",
    document: report.patient?.document || report.patientDocument || stored.document || "",
  };
}

export function hydrateReportPatient(report: SessionReportRecord): SessionReportRecord {
  const patient = getReportPatient(report);
  return {
    ...report,
    patient,
    patientId: patient.id || report.patientId,
    patientName: patient.name || report.patientName,
    patientDocument: patient.document || report.patientDocument,
  };
}

export function patientGroupKey(patient: PatientIdentity, fallback: string) {
  return (
    patient.id ||
    patient.email ||
    patient.phone ||
    patient.document ||
    patient.name ||
    fallback
  )
    .toString()
    .trim()
    .toLowerCase();
}

export function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}min ${rest.toString().padStart(2, "0")}s`;
}
