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
      label: "Z Domin.",
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
    { key: "f0", label: "F0 Med.", value: fmt(snapshot.f0Mean, 1) },
    { key: "zcr", label: "ZCR", value: fmt(snapshot.zcr, 3) },
    { key: "jitter", label: "Jitter", value: fmt(snapshot.jitter, 3) },
    { key: "shimmer", label: "Shimmer", value: fmt(snapshot.shimmer, 3) },
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
