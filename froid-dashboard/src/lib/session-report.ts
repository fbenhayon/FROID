import { PerceptionZone } from "./froid-engine";

export interface ClinicalNote {
  id: string;
  text: string;
  timestamp: number;
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
  zones: PerceptionZone[];
}

export interface SessionReportRecord {
  id: string;
  sessionId: string;
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
  dissonances: Array<{
    id: string;
    timestamp: string;
    elapsedSeconds: number;
    zone: number;
    report: string;
  }>;
  transcript: string;
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

export function loadSessionReports(): SessionReportRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(REPORT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSessionReport(report: SessionReportRecord) {
  if (typeof window === "undefined") return;
  const reports = loadSessionReports();
  const next = [
    report,
    ...reports.filter((item) => item.sessionId !== report.sessionId),
  ].slice(0, 100);
  window.localStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(next));
}

export function loadSessionReport(sessionId: string) {
  return loadSessionReports().find((report) => report.sessionId === sessionId);
}

export function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}min ${rest.toString().padStart(2, "0")}s`;
}
