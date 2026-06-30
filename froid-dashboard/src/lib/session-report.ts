import { PerceptionZone } from "./froid-engine";

export interface ClinicalNote {
  id: string;
  text: string;
  timestamp: number;
}

export interface PatientIdentity {
  id?: string;
  name?: string;
  email?: string;
  phone?: string;
  document?: string;
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
  f0Mean: number | null;
  zcr: number | null;
  jitter: number | null;
  shimmer: number | null;
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
  conversationSummaries: Array<{
    id: string;
    startMinute: number;
    endMinute: number;
    theme: string;
    summary: string;
  }>;
  sessionSummary?: {
    theme: string;
    summary: string;
    generatedAt: string;
  };
  dissonances: Array<{
    id: string;
    timestamp: string;
    elapsedSeconds: number;
    zone: number;
    report: string;
  }>;
  transcript: string;
  transcriptRetention?: "disabled_summary_only" | "enabled";
  anonymizedContext?: {
    schemaVersion: string;
    sessionModality: "remote" | "presential" | "unknown";
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
    }>;
  };
  metricsAnalysis?: MetricsAnalysis;
  metricsAnalysisError?: string;
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
    last_risk: number | null;
    max_risk: number | null;
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
    clinical_risk: number | null;
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
