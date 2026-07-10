import {
  getReportPatient,
  MetricSnapshot,
  patientGroupKey,
  PatientIdentity,
  SessionReportRecord,
} from "./session-report";

export interface PatientDashboardGroup {
  key: string;
  patient: PatientIdentity;
  reports: SessionReportRecord[];
  latestReport: SessionReportRecord;
  totalSessions: number;
  completedSessions: number;
  activeSessions: number;
  totalAnalyses: number;
  dominantZone: number | null;
  recurrentEmotion: string;
  clinicalRisk: string;
  facsSummary: string;
  riskTypes: string;
  clinicalNote: string;
}

export interface PatientAdvancedSignal {
  state: string;
  priority: "ALTA PRIORIDADE" | "REVISAR" | "OBSERVAR" | "ROTINA" | "DADOS INSUFICIENTES";
  action: string;
  attentionIndex: number;
  clinicalLoad: number;
  communication: number;
  continuity: number;
  insight: number;
  dataQuality: number;
  ipmTrend: number;
  idmRecent: number;
  qualityLabel: string;
}

export interface ProfessionalPortfolioSummary {
  totalPatients: number;
  meanAttention: number;
  meanClinicalLoad: number;
  meanCommunication: number;
  meanContinuity: number;
  meanInsight: number;
  reviewCount: number;
}

export function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return Number(value).toFixed(digits);
}

export function fmtDelta(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(digits)}`;
}

export function limitWords(text: string, maxWords: number) {
  return String(text || "").trim().split(/\s+/).filter(Boolean).slice(0, maxWords).join(" ");
}

export function reportStartDate(report: SessionReportRecord) {
  const end = new Date(report.createdAt || Date.now());
  return new Date(end.getTime() - Math.max(0, report.durationSeconds || 0) * 1000);
}

export function reportEndDate(report: SessionReportRecord) {
  return new Date(report.createdAt || Date.now());
}

export function formatDateTime(date: Date) {
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortId(value: string) {
  return value ? `${value.slice(0, 8)}...` : "--";
}

export interface SessionMetricCell {
  key: string;
  label: string;
  value: string;
}

export function sessionMetricCells(
  snapshot: MetricSnapshot,
  themeOverride?: string,
): SessionMetricCell[] {
  return [
    { key: "ipm", label: "IPM", value: fmt(snapshot.ipmAvg, 1) },
    { key: "idm", label: "IDM", value: fmt(snapshot.idmAvg, 2) },
    {
      key: "zone",
      label: "ZONAS",
      value: snapshot.dominantZone ? String(snapshot.dominantZone) : "--",
    },
    {
      key: "theme",
      label: "Tema",
      value: limitWords(themeOverride || snapshot.theme || snapshot.dominantTheme, 6) || "--",
    },
    { key: "tone", label: "Tom", value: snapshot.emotionalTone || "--" },
    { key: "wpm", label: "P/min", value: fmt(snapshot.wordsPerMinute, 0) },
    { key: "dissonance", label: "Disso.", value: String(snapshot.dissonanceCount || 0) },
    { key: "mfcc7", label: "MFCC7", value: fmt(snapshot.mfcc7, 2) },
    { key: "mfcc9", label: "MFCC9", value: fmt(snapshot.mfcc9, 2) },
    { key: "dmfcc7", label: "DMFCC7", value: fmt(snapshot.mfcc7Delta, 3) },
    { key: "beta", label: "Beta", value: fmt(snapshot.spectralBeta12_30, 2) },
    { key: "gamma", label: "Gama", value: fmt(snapshot.spectralGamma30_80, 2) },
    { key: "f0", label: "F0 Med.", value: fmt(snapshot.f0Mean, 1) },
    { key: "zcr", label: "ZCR", value: fmt(snapshot.zcr, 3) },
    { key: "jitter", label: "Jitter idx.", value: fmt(snapshot.jitter, 3) },
    { key: "shimmer", label: "Shimmer idx.", value: fmt(snapshot.shimmer, 3) },
    { key: "sub5", label: "Sub-H 5-12Hz", value: fmt(snapshot.subharmonic5_12, 2) },
    { key: "sub12", label: "Sub-H 12-20Hz", value: fmt(snapshot.subharmonic12_20, 2) },
  ];
}

export function sessionResultText(report: SessionReportRecord, maxWords = 120) {
  const summary =
    report.sessionSummary?.summary ||
    report.conversationSummaries?.[0]?.summary ||
    report.metricsAnalysis?.dashboard.data_status ||
    report.sessionAverage.theme ||
    "Resultado da sessao ainda nao consolidado.";
  return limitWords(summary, maxWords);
}

export function splitSessionResult(report: SessionReportRecord) {
  const words = sessionResultText(report, 120).split(/\s+/).filter(Boolean);
  const midpoint = Math.ceil(words.length / 2);
  return [
    words.slice(0, midpoint).join(" ") || "Resultado da sessao ainda nao consolidado.",
    words.slice(midpoint).join(" "),
  ];
}

export function paymentStatusForReport(report: SessionReportRecord) {
  const source = report as SessionReportRecord & {
    payment?: { payment_status?: string; status?: string };
    paymentStatus?: string;
    payment_status?: string;
  };
  const raw =
    source.payment?.payment_status ||
    source.payment?.status ||
    source.paymentStatus ||
    source.payment_status ||
    "";
  const normalized = String(raw).toLowerCase();
  if (["paid", "pago", "approved", "aprovado", "settled"].some((word) => normalized.includes(word))) {
    return "Pago";
  }
  if (["package", "pacote", "prepaid", "pre-pago"].some((word) => normalized.includes(word))) {
    return "Pacote";
  }
  return "Em aberto";
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function average(values: Array<number | null | undefined>, fallback = 0) {
  const clean = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!clean.length) return fallback;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function qualityFromReport(report: SessionReportRecord) {
  const dashboard = report.metricsAnalysis?.dashboard;
  const confidence =
    typeof dashboard?.mean_confidence === "number" ? dashboard.mean_confidence : null;
  const coverage =
    typeof dashboard?.mean_coverage === "number" ? dashboard.mean_coverage : null;
  const cutCoverage =
    (report.tenMinuteCuts || []).filter((cut) => (cut.sampleCount || 0) > 0).length /
    Math.max(1, (report.tenMinuteCuts || []).length || 1);
  const transcriptSignal =
    report.transcriptRetention === "disabled_summary_only" ||
    report.conversationSummaries?.length ||
    report.sessionSummary
      ? 0.82
      : 0.52;
  return clamp(
    average([confidence, coverage, cutCoverage, transcriptSignal], 0.6) * 100,
    0,
    100,
  );
}

function stateFromMetrics(ipm: number, idm: number, quality: number) {
  if (quality < 45) return "DADOS INSUFICIENTES";
  if (ipm <= 35 && idm <= -0.65) return "BAIXA ENERGIA + NEGATIVO";
  if (ipm >= 55 && idm <= -0.45) return "SOFRIMENTO ATIVO";
  if (ipm <= 35 && idm < 0.15) return "EMBOTAMENTO / DEFESA";
  if (ipm >= 55 && idm >= 0.15) return "FLUXO SAUDAVEL";
  if (idm >= 0.35) return "ADAPTATIVO";
  return "ATENCAO";
}

function qualityLabel(score: number) {
  if (score >= 85) return "COMPLETO";
  if (score >= 60) return "PARCIAL";
  if (score >= 45) return "BAIXA ROBUSTEZ";
  return "NAO PROCESSADO";
}

export function patientAdvancedSignal(group: PatientDashboardGroup): PatientAdvancedSignal {
  const reports = group.reports || [];
  const recent = reports.slice(0, 3);
  const latest = group.latestReport;
  const latestAverage = latest.sessionAverage;
  const ipmRecent = average(recent.map((report) => report.sessionAverage.ipmAvg), latestAverage.ipmAvg);
  const idmRecent = average(recent.map((report) => report.sessionAverage.idmAvg), latestAverage.idmAvg);
  const firstRecent = recent[recent.length - 1]?.sessionAverage.ipmAvg ?? ipmRecent;
  const lastRecent = recent[0]?.sessionAverage.ipmAvg ?? ipmRecent;
  const ipmTrend = lastRecent - firstRecent;
  const dataQuality = average(recent.map(qualityFromReport), qualityFromReport(latest));
  const maxRisk = Math.max(
    0,
    ...recent.map((report) => report.metricsAnalysis?.dashboard.max_risk || 0),
    ...recent.map((report) => (report.sessionAverage.dissonanceCount || 0) * 18),
  );
  const dissonance = average(
    recent.map((report) => report.sessionAverage.dissonanceCount || 0),
    0,
  );
  const negativeDirection = clamp(-idmRecent, 0, 1) * 100;
  const lowEnergyNegative =
    (clamp(35 - ipmRecent, 0, 35) / 35) * clamp(-idmRecent, 0, 1) * 100;
  const clinicalLoad = clamp(
    ipmRecent * 0.22 +
      negativeDirection * 0.34 +
      lowEnergyNegative * 0.22 +
      dissonance * 4 +
      maxRisk * 0.18 +
      clamp(75 - dataQuality, 0, 75) * 0.24,
    0,
    100,
  );
  const summarizedCuts = recent.reduce(
    (sum, report) => sum + (report.conversationSummaries?.length || 0),
    0,
  );
  const communication = clamp(
    42 +
      summarizedCuts * 8 +
      Math.min(18, group.completedSessions * 3) +
      (latest.clinicalNotes?.length || 0) * 4,
    0,
    100,
  );
  const continuity = clamp(
    35 +
      Math.min(36, group.totalSessions * 6) +
      Math.min(16, group.totalAnalyses * 2) -
      (paymentStatusForReport(latest) === "Em aberto" ? 6 : 0),
    0,
    100,
  );
  const insight = clamp(
    communication * 0.24 +
      continuity * 0.16 +
      dataQuality * 0.22 +
      clamp(100 - Math.abs(clinicalLoad - 58), 0, 100) * 0.28 +
      clamp(Math.abs(ipmTrend) * 4, 0, 20) -
      clamp(-idmRecent, 0, 1) * 18,
    0,
    100,
  );
  const attentionIndex = clamp(
    clinicalLoad * 0.38 +
      (100 - communication) * 0.18 +
      (100 - continuity) * 0.18 +
      (100 - dataQuality) * 0.13 +
      insight * 0.13,
    0,
    100,
  );
  const state = stateFromMetrics(ipmRecent, idmRecent, dataQuality);
  const priority: PatientAdvancedSignal["priority"] =
    state === "DADOS INSUFICIENTES" || dataQuality < 45
      ? "DADOS INSUFICIENTES"
      : attentionIndex >= 72
        ? "ALTA PRIORIDADE"
        : attentionIndex >= 58
          ? "REVISAR"
          : attentionIndex >= 42
            ? "OBSERVAR"
            : "ROTINA";
  const action =
    priority === "ALTA PRIORIDADE"
      ? "Revisao clinica prioritaria"
      : priority === "REVISAR"
        ? "Revisar proximos cortes e anotacoes"
        : priority === "OBSERVAR"
          ? "Acompanhar tendencia longitudinal"
          : priority === "DADOS INSUFICIENTES"
            ? "Revisar qualidade de coleta"
            : "Rotina de acompanhamento";

  return {
    state,
    priority,
    action,
    attentionIndex,
    clinicalLoad,
    communication,
    continuity,
    insight,
    dataQuality,
    ipmTrend,
    idmRecent,
    qualityLabel: qualityLabel(dataQuality),
  };
}

export function professionalPortfolioSummary(
  groups: PatientDashboardGroup[],
): ProfessionalPortfolioSummary {
  const signals = groups.map(patientAdvancedSignal);
  return {
    totalPatients: groups.length,
    meanAttention: average(signals.map((signal) => signal.attentionIndex), 0),
    meanClinicalLoad: average(signals.map((signal) => signal.clinicalLoad), 0),
    meanCommunication: average(signals.map((signal) => signal.communication), 0),
    meanContinuity: average(signals.map((signal) => signal.continuity), 0),
    meanInsight: average(signals.map((signal) => signal.insight), 0),
    reviewCount: signals.filter((signal) =>
      ["ALTA PRIORIDADE", "REVISAR"].includes(signal.priority),
    ).length,
  };
}

function mostFrequent<T extends string | number>(values: T[]): T | null {
  const counts = new Map<T, number>();
  values
    .filter((value) => value !== "" && value !== null && value !== undefined)
    .forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  let selected: T | null = null;
  let selectedCount = 0;
  counts.forEach((count, value) => {
    if (count > selectedCount) {
      selected = value;
      selectedCount = count;
    }
  });
  return selected;
}

function riskScore(report: SessionReportRecord) {
  const risk = report.metricsAnalysis?.dashboard.max_risk;
  if (typeof risk === "number" && Number.isFinite(risk)) return risk;
  return Math.min(100, (report.sessionAverage.dissonanceCount || 0) * 18);
}

function riskLabel(score: number) {
  if (score >= 70) return "Alto";
  if (score >= 40) return "Moderado";
  return "Baixo";
}

function totalAnalysisWindows(report: SessionReportRecord) {
  const populated = report.metricsAnalysis?.dashboard.populated_windows;
  if (typeof populated === "number" && Number.isFinite(populated)) return populated;
  return (report.tenMinuteCuts || []).filter((cut) => (cut.sampleCount || 0) > 0).length;
}

function buildClinicalNote(
  patientName: string,
  dominantZone: number | null,
  recurrentEmotion: string,
  clinicalRisk: string,
  sessionCount: number,
) {
  const zoneText = dominantZone ? `zona ${dominantZone}` : "zona ainda indefinida";
  const emotionText =
    recurrentEmotion && recurrentEmotion !== "--"
      ? `com tom recorrente ${recurrentEmotion.toLowerCase()}`
      : "com tom recorrente ainda em consolidacao";
  return `${patientName} apresenta padrao longitudinal baseado em ${sessionCount} sessao(oes), com predominancia de ${zoneText}, ${emotionText} e risco clinico ${clinicalRisk.toLowerCase()}. Recomenda-se acompanhar a evolucao comparando baseline, media da sessao e cortes de 10 minutos.`;
}

export function buildPatientGroups(reports: SessionReportRecord[]): PatientDashboardGroup[] {
  const buckets = new Map<string, SessionReportRecord[]>();

  reports.forEach((report) => {
    const patient = getReportPatient(report);
    const key = patientGroupKey(patient, report.sessionId);
    buckets.set(key, [...(buckets.get(key) || []), { ...report, patient }]);
  });

  return Array.from(buckets.entries())
    .map(([key, patientReports]) => {
      const sorted = [...patientReports].sort(
        (a, b) =>
          new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime(),
      );
      const latestReport = sorted[0];
      const patient = getReportPatient(latestReport);
      const dominantZone = mostFrequent(
        sorted
          .map((report) => report.sessionAverage?.dominantZone || report.baseline?.dominantZone)
          .filter((zone): zone is number => typeof zone === "number"),
      );
      const recurrentEmotion =
        mostFrequent(
          sorted
            .map((report) => report.sessionAverage?.emotionalTone || report.baseline?.emotionalTone || "")
            .filter(Boolean),
        ) || "--";
      const maxRisk = Math.max(0, ...sorted.map(riskScore));
      const clinicalRisk = riskLabel(maxRisk);
      const dissonanceCount = sorted.reduce(
        (sum, report) => sum + (report.dissonances?.length || report.sessionAverage.dissonanceCount || 0),
        0,
      );
      const totalAnalyses = sorted.reduce(
        (sum, report) => sum + totalAnalysisWindows(report),
        0,
      );
      const patientName = patient.name || "Paciente sem nome";

      return {
        key,
        patient,
        reports: sorted,
        latestReport,
        totalSessions: sorted.length,
        completedSessions: sorted.length,
        activeSessions: 0,
        totalAnalyses,
        dominantZone,
        recurrentEmotion,
        clinicalRisk,
        facsSummary:
          dissonanceCount > 0
            ? `${dissonanceCount} dissonancia(s) facial-vocal registrada(s)`
            : "Sem dissonancia facial-vocal critica",
        riskTypes: "Depressao / Mania / Estresse",
        clinicalNote: buildClinicalNote(
          patientName,
          dominantZone,
          recurrentEmotion,
          clinicalRisk,
          sorted.length,
        ),
      };
    })
    .sort(
      (a, b) =>
        new Date(b.latestReport.createdAt || 0).getTime() -
        new Date(a.latestReport.createdAt || 0).getTime(),
    );
}

export function mergeReports(
  localReports: SessionReportRecord[],
  remoteReports: SessionReportRecord[],
) {
  const bySession = new Map<string, SessionReportRecord>();
  [...remoteReports, ...localReports].forEach((report) => {
    if (!report?.sessionId) return;
    const previous = bySession.get(report.sessionId);
    bySession.set(report.sessionId, {
      ...(previous || {}),
      ...report,
      patient: {
        ...(previous?.patient || {}),
        ...(report.patient || {}),
      },
    });
  });
  return Array.from(bySession.values()).sort(
    (a, b) =>
      new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime(),
  );
}
