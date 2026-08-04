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
  dissonanceCount: number;
  facsSummary: string;
  clinicalNote: string;
}

export interface PatientAdvancedSignal {
  state: string;
  priority: "ALTA PRIORIDADE" | "REVISAR" | "OBSERVAR" | "ROTINA" | "DADOS INSUFICIENTES";
  action: string;
  attentionIndex: number;
  signalLoad: number;
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
  meanSignalLoad: number;
  meanCommunication: number;
  meanContinuity: number;
  meanInsight: number;
  reviewCount: number;
}

const SEARCH_ACCENT_MAP: Record<string, string> = {
  a: "aàáâãä",
  e: "eèéêë",
  i: "iìíîï",
  o: "oòóôõö",
  u: "uùúûü",
  c: "cç",
  n: "nñ",
};
const SEARCH_ACCENT_PATTERN = new RegExp(
  Object.values(SEARCH_ACCENT_MAP).map((chars) => `[${chars.slice(1)}]`).join("|"),
  "g",
);

export function normalizeSearchText(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(SEARCH_ACCENT_PATTERN, (char) => {
      const base = Object.keys(SEARCH_ACCENT_MAP).find((key) =>
        SEARCH_ACCENT_MAP[key].includes(char),
      );
      return base || char;
    });
}

export function matchesPatientSearch(
  group: PatientDashboardGroup,
  query: string,
) {
  const queryTokens = normalizeSearchText(query).split(/\s+/).filter(Boolean);
  if (!queryTokens.length) return true;
  const haystack = normalizeSearchText(
    [
      group.patient.name,
      group.patient.email,
      group.patient.phone,
      group.patient.document,
    ]
      .filter(Boolean)
      .join(" "),
  );
  // Cada palavra digitada precisa aparecer em algum lugar (não necessariamente
  // contígua), para achar "Ana Souza" mesmo quando o nome completo é "Ana
  // Cecília Souza".
  return queryTokens.every((token) => haystack.includes(token));
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
    "Resultado da sessão ainda não consolidado.";
  return limitWords(summary, maxWords);
}

export function splitSessionResult(report: SessionReportRecord) {
  const words = sessionResultText(report, 120).split(/\s+/).filter(Boolean);
  const midpoint = Math.ceil(words.length / 2);
  return [
    words.slice(0, midpoint).join(" ") || "Resultado da sessão ainda não consolidado.",
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

// A mesma partição de antes, descrita pelo que ela é.
//
// Os rótulos anteriores — "SOFRIMENTO ATIVO", "EMBOTAMENTO / DEFESA",
// "FLUXO SAUDAVEL" — nomeavam estado clínico do paciente a partir de duas
// medidas. Nenhum corte muda aqui: as mesmas faixas de IPM e IDM produzem as
// mesmas seis categorias. O que muda é que a categoria passa a dizer o que
// o sinal fez, em vez de concluir sobre a pessoa.
//
// É mais informativo assim: "ENERGIA ALTA + DESVIO NEGATIVO" diz ao clínico
// o que as métricas fizeram; "SOFRIMENTO ATIVO" dizia a ele uma conclusão que
// é dele, não do software.
function stateFromMetrics(ipm: number, idm: number, quality: number) {
  if (quality < 45) return "DADOS INSUFICIENTES";
  if (ipm <= 35 && idm <= -0.65) return "ENERGIA BAIXA + DESVIO MUITO NEGATIVO";
  if (ipm >= 55 && idm <= -0.45) return "ENERGIA ALTA + DESVIO NEGATIVO";
  if (ipm <= 35 && idm < 0.15) return "ENERGIA BAIXA + DESVIO NEUTRO";
  if (ipm >= 55 && idm >= 0.15) return "ENERGIA ALTA + DESVIO POSITIVO";
  if (idm >= 0.35) return "DESVIO POSITIVO";
  return "PADRÃO INTERMEDIÁRIO";
}

function qualityLabel(score: number) {
  if (score >= 85) return "COMPLETO";
  if (score >= 60) return "PARCIAL";
  if (score >= 45) return "BAIXA ROBUSTEZ";
  return "NÃO PROCESSADO";
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
  // Antes este máximo combinava dashboard.max_risk — o escore "Risco clínico"
  // que saiu do motor — com a carga de dissonância. Restou a segunda, que é a
  // única das duas que era medida.
  const maxDissonanceLoad = Math.max(0, ...recent.map(dissonanceLoad));
  const dissonance = average(
    recent.map((report) => report.sessionAverage.dissonanceCount || 0),
    0,
  );
  const negativeDirection = clamp(-idmRecent, 0, 1) * 100;
  const lowEnergyNegative =
    (clamp(35 - ipmRecent, 0, 35) / 35) * clamp(-idmRecent, 0, 1) * 100;
  const signalLoad = clamp(
    ipmRecent * 0.22 +
      negativeDirection * 0.34 +
      lowEnergyNegative * 0.22 +
      dissonance * 4 +
      maxDissonanceLoad * 0.18 +
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
      clamp(100 - Math.abs(signalLoad - 58), 0, 100) * 0.28 +
      clamp(Math.abs(ipmTrend) * 4, 0, 20) -
      clamp(-idmRecent, 0, 1) * 18,
    0,
    100,
  );
  const attentionIndex = clamp(
    signalLoad * 0.38 +
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
      ? "Revisão clínica prioritária"
      : priority === "REVISAR"
        ? "Revisar próximos cortes e anotações"
        : priority === "OBSERVAR"
          ? "Acompanhar tendência longitudinal"
          : priority === "DADOS INSUFICIENTES"
            ? "Revisar qualidade de coleta"
            : "Rotina de acompanhamento";

  return {
    state,
    priority,
    action,
    attentionIndex,
    signalLoad,
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
    meanSignalLoad: average(signals.map((signal) => signal.signalLoad), 0),
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

// Carga de dissonância registrada na sessão, normalizada em 0-100.
//
// Aqui existia riskScore(), que lia dashboard.max_risk — o escore "Risco
// clínico" que saiu do motor — e riskLabel(), que o cortava em Alto/Moderado/
// Baixo. Classificar uma pessoa em faixa de risco é triagem, e triagem é ato
// privativo de profissional habilitado.
//
// O que sobra é o que sempre foi medido de fato: quantos eventos de
// dissonância facial-vocal foram confirmados. É contagem, não julgamento.
function dissonanceLoad(report: SessionReportRecord) {
  return Math.min(100, (report.sessionAverage.dissonanceCount || 0) * 18);
}

function totalAnalysisWindows(report: SessionReportRecord) {
  const populated = report.metricsAnalysis?.dashboard.populated_windows;
  if (typeof populated === "number" && Number.isFinite(populated)) return populated;
  return (report.tenMinuteCuts || []).filter((cut) => (cut.sampleCount || 0) > 0).length;
}

// Resumo de medida, não parecer.
//
// A versão anterior escrevia, ao lado do nome do paciente, "risco clínico
// alto" — inferência sobre a pessoa, assinada pelo software. O fecho
// ("compare baseline, média e cortes") não é conduta clínica e sim instrução
// de leitura da ferramenta, então permanece.
function buildMeasurementNote(
  patientName: string,
  dominantZone: number | null,
  recurrentEmotion: string,
  dissonanceCount: number,
  sessionCount: number,
) {
  const zoneText = dominantZone ? `zona ${dominantZone}` : "zona predominante ainda indefinida";
  const emotionText =
    recurrentEmotion && recurrentEmotion !== "--"
      ? `, tom recorrente ${recurrentEmotion.toLowerCase()}`
      : "";
  const dissonanceText =
    dissonanceCount > 0
      ? `${dissonanceCount} evento(s) de dissonância facial-vocal confirmado(s)`
      : "nenhum evento de dissonância facial-vocal confirmado";
  return `${patientName}: ${sessionCount} sessão(ões) analisada(s), ${zoneText}${emotionText}. ${dissonanceText}. Compare a linha de base, a média da sessão e os cortes de 10 minutos para acompanhar a evolução.`;
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
        dissonanceCount,
        facsSummary:
          dissonanceCount > 0
            ? `${dissonanceCount} dissonância(s) facial-vocal registrada(s)`
            : "Sem dissonância facial-vocal registrada",
        clinicalNote: buildMeasurementNote(
          patientName,
          dominantZone,
          recurrentEmotion,
          dissonanceCount,
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
