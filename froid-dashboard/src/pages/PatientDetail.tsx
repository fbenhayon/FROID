import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  fmtDelta,
  formatDateTime,
  mergeReports,
  patientAdvancedSignal,
  paymentStatusForReport,
  reportEndDate,
  reportStartDate,
  sessionMetricCells,
  splitSessionResult,
  shortId,
} from "../lib/patient-dashboard";
import {
  formatDuration,
  loadSessionReports,
  MetricSnapshot,
  SessionReportRecord,
} from "../lib/session-report";

function detailMetricCells(snapshot: MetricSnapshot) {
  return sessionMetricCells(snapshot).filter((cell) => cell.key !== "theme");
}

export const PatientDetail: React.FC = () => {
  const navigate = useNavigate();
  const { patientKey = "" } = useParams<{ patientKey: string }>();
  const decodedPatientKey = decodeURIComponent(patientKey);
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );

  useEffect(() => {
    let active = true;
    fetch(apiUrl("/api/session-reports"))
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active) return;
        const remoteReports: SessionReportRecord[] = Array.isArray(data?.reports)
          ? data.reports
          : Array.isArray(data)
            ? data
            : [];
        if (remoteReports.length) {
          setReports((current) => mergeReports(current, remoteReports));
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const group = useMemo(
    () => buildPatientGroups(reports).find((item) => item.key === decodedPatientKey),
    [decodedPatientKey, reports],
  );

  if (!group) {
    return (
      <div className="min-h-screen bg-white p-1 text-black">
        <button
          onClick={() => navigate("/dashboard")}
          className="border border-black px-2 py-0.5 text-[10px]"
        >
          Voltar ao Dashboard
        </button>
        <h1 className="mt-5 text-xl font-bold">Paciente nao encontrado</h1>
        <p className="mt-2 text-xs">
          Ainda nao ha relatorios locais ou sincronizados para este paciente.
        </p>
      </div>
    );
  }

  const latest = group.latestReport;
  const context = {
    patient: group.patient,
    patient_summary: {
      total_sessions: group.totalSessions,
      completed_sessions: group.completedSessions,
      active_sessions: group.activeSessions,
      total_analyses: group.totalAnalyses,
      dominant_zone: group.dominantZone,
      recurrent_emotion: group.recurrentEmotion,
      clinical_risk: group.clinicalRisk,
      clinical_note: group.clinicalNote,
    },
    latest_report_baseline: latest.baseline,
    latest_report_average: latest.sessionAverage,
    latest_report_cuts: latest.tenMinuteCuts,
  };
  const signal = patientAdvancedSignal(group);

  return (
    <div className="min-h-screen bg-slate-50 p-4 text-slate-800">
      <button
        onClick={() => navigate("/dashboard")}
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100"
      >
        Voltar ao Dashboard
      </button>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-blue-600">
            Dashboard Longitudinal do Paciente
          </p>
          <h1 className="mt-1 text-2xl font-bold">
            {group.patient.name || "Paciente sem nome"}
          </h1>
          <p className="mt-2 text-xs text-slate-500">
            CPF: {group.patient.document || "Nao informado"}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-black text-blue-700">
            {signal.priority}
          </span>
          <button
            onClick={() => navigate(`/session/${latest.sessionId}`)}
            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
          >
            Enviar convite / abrir sessao
          </button>
        </div>
      </div>

      <section className="mt-5 grid gap-3 md:grid-cols-4 xl:grid-cols-8">
        <PatientKpi label="Total de Sessoes" value={String(group.totalSessions)} />
        <PatientKpi label="Concluidas" value={String(group.completedSessions)} />
        <PatientKpi label="Ativas" value={String(group.activeSessions)} />
        <PatientKpi label="Analises" value={String(group.totalAnalyses)} />
        <PatientKpi label="Atencao" value={`${Math.round(signal.attentionIndex)}/100`} tone="red" />
        <PatientKpi label="Qualidade" value={signal.qualityLabel} tone="green" />
        <PatientKpi label="Comunicacao" value={`${Math.round(signal.communication)}/100`} tone="blue" />
        <PatientKpi label="Insight" value={`${Math.round(signal.insight)}/100`} tone="violet" />
      </section>
      </div>

      <section className="sticky top-0 z-20 mt-4 rounded-2xl border border-emerald-300 bg-emerald-50/95 p-4 shadow-sm backdrop-blur">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-emerald-950">FROID Explica</h2>
            <p className="mt-0.5 text-[11px] text-emerald-800">
              Consulta longitudinal fixa para este paciente.
            </p>
          </div>
          <button
            onClick={() => navigate("/settings")}
            className="rounded-lg border border-cyan-200 bg-cyan-50 px-3 py-1.5 text-[11px] font-bold text-cyan-800 hover:bg-cyan-100"
          >
            Meus Prompts...
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto rounded-lg border border-emerald-200 bg-white/80 px-2 pb-2 pr-1">
          <AIInsights
            zones={latest.sessionAverage.zones || []}
            ipmScore={latest.sessionAverage.ipmAvg}
            coherenceStatus={latest.sessionAverage.coherenceStatus}
            baselineEstablished
            sessionId={latest.sessionId}
            extraContext={context}
            controlsSticky
            rootClassName="border-0"
            messagesClassName="min-h-36 max-h-52"
          />
        </div>
      </section>

      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Evolucao das ultimas 20 sessoes</h2>
            <p className="mt-1 text-xs text-slate-500">
              IPM, IDM, palavras por minuto, dissonancias e sub-harmonicos em escala propria.
            </p>
          </div>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-black uppercase text-slate-500">
            {signal.state}
          </span>
        </div>
        <PatientEvolutionChart reports={group.reports} />
      </section>

      <div className="mt-5">
        <main className="min-w-0">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-bold">Indicadores Clinicos</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <Indicator
                label="Zona FROID Dominante"
                value={group.dominantZone ? `Zona ${group.dominantZone}` : "--"}
                detail={`Baseado em ${group.completedSessions} sessoes`}
              />
              <Indicator
                label="Emocao Recorrente"
                value={group.recurrentEmotion || "--"}
                detail="FACS - Analise Facial"
              />
              <Indicator
                label="Risco Clinico"
                value={group.clinicalRisk}
                detail={group.riskTypes}
              />
            </div>
            <p className="mt-4 text-xs">
              <strong>Nota Clinica:</strong> {group.clinicalNote}
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-5">
              <PatientScoreBar label="Carga clinica" value={signal.clinicalLoad} color="#f97316" />
              <PatientScoreBar label="Comunicacao" value={signal.communication} color="#0ea5e9" />
              <PatientScoreBar label="Continuidade" value={signal.continuity} color="#22c55e" />
              <PatientScoreBar label="Insight" value={signal.insight} color="#8b5cf6" />
              <PatientScoreBar label="Qualidade" value={signal.dataQuality} color="#14b8a6" />
            </div>
            <p className="mt-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-900">
              Linha comparativa: IPM {fmt(latest.baseline.ipmAvg, 1)} -&gt;{" "}
              {fmt(latest.sessionAverage.ipmAvg, 1)} (
              {fmtDelta(latest.sessionAverage.ipmAvg - latest.baseline.ipmAvg, 1)})
              {" | "}IDM {fmt(latest.baseline.idmAvg, 2)} -&gt;{" "}
              {fmt(latest.sessionAverage.idmAvg, 2)}
            </p>
          </section>

          <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-bold">Sessoes realizadas</h2>
            <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200">
              <table className="min-w-[1500px] w-full border-collapse text-left text-[10px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 font-bold uppercase text-slate-400">
                    <th className="px-1 py-1">Data</th>
                    <th className="px-1 py-1">Sessao</th>
                    {detailMetricCells(latest.sessionAverage).map((cell) => (
                      <th key={cell.key} className="px-1 py-1">
                        {cell.label}
                      </th>
                    ))}
                    <th className="px-1 py-1">Pagamento</th>
                    <th className="px-1 py-1">Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {group.reports.map((report) => {
                    const resultLines = splitSessionResult(report);
                    return (
                      <React.Fragment key={report.sessionId}>
                        <tr className="border-b border-slate-200 align-top odd:bg-white even:bg-slate-50">
                          <td className="px-1 py-1">
                            {formatDateTime(reportEndDate(report))}
                          </td>
                          <td className="px-1 py-1">{shortId(report.sessionId)}</td>
                          {detailMetricCells(report.sessionAverage).map((cell) => (
                            <td key={cell.key} className="px-1 py-1">
                              {cell.value}
                            </td>
                          ))}
                          <td className="px-1 py-1 font-bold">
                            {paymentStatusForReport(report)}
                          </td>
                          <td className="px-1 py-1">
                            <button
                              onClick={() =>
                                navigate(`/session/${report.sessionId}/report`)
                              }
                              className="rounded border border-slate-200 bg-white px-2 py-1 font-bold text-slate-600 hover:bg-slate-50"
                            >
                              Ver
                            </button>
                          </td>
                        </tr>
                        <tr className="border-b border-slate-100 bg-blue-50/60">
                          <td colSpan={18} className="px-2 py-2 text-xs">
                            <strong>Resultado da sessao:</strong> {resultLines[0]}
                          </td>
                        </tr>
                        <tr className="border-b border-slate-200 bg-blue-50/40">
                          <td colSpan={18} className="px-2 py-2 text-xs">
                            {resultLines[1] || "Complemento ainda nao consolidado."}
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-bold">Historico de Sessoes</h2>
            <table className="mt-3 w-full table-fixed text-left text-xs">
              <thead>
                <tr className="font-bold">
                  <th className="w-[13%]">ID</th>
                  <th className="w-[12%]">STATUS</th>
                  <th className="w-[23%]">INICIO</th>
                  <th className="w-[23%]">FIM</th>
                  <th className="w-[17%]">DURACAO</th>
                  <th>ANALISES</th>
                </tr>
              </thead>
              <tbody>
                {group.reports.map((report, index) => (
                  <tr key={report.sessionId}>
                    <td>
                      <button
                        onClick={() =>
                          navigate(`/session/${report.sessionId}/report`)
                        }
                        className="underline-offset-2 hover:underline"
                      >
                        {shortId(report.sessionId)}
                      </button>
                    </td>
                    <td>{index === 0 ? "Concluida" : "Ativa"}</td>
                    <td>{formatDateTime(reportStartDate(report))}</td>
                    <td>{formatDateTime(reportEndDate(report))}</td>
                    <td>{formatDuration(report.durationSeconds)}</td>
                    <td>
                      {report.metricsAnalysis?.dashboard.populated_windows ||
                        report.tenMinuteCuts.filter((cut) => cut.sampleCount > 0)
                          .length}{" "}
                      registros
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
};

const PatientKpi: React.FC<{
  label: string;
  value: string;
  tone?: "blue" | "green" | "red" | "violet";
}> = ({ label, value, tone = "blue" }) => {
  const color =
    tone === "green"
      ? "text-emerald-300"
      : tone === "red"
        ? "text-red-300"
        : tone === "violet"
          ? "text-violet-300"
          : "text-cyan-300";
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-white">
      <p className="text-[9px] font-black uppercase tracking-widest text-slate-400">
        {label}
      </p>
      <p className={`mt-2 text-lg font-black ${color}`}>{value}</p>
    </div>
  );
};

const PatientScoreBar: React.FC<{
  label: string;
  value: number;
  color: string;
}> = ({ label, value, color }) => (
  <div>
    <div className="mb-1 flex items-center justify-between gap-2 text-[10px] font-bold uppercase text-slate-500">
      <span>{label}</span>
      <span>{Math.round(value)}/100</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
      <div
        className="h-full rounded-full"
        style={{ width: `${Math.max(4, Math.min(100, value))}%`, backgroundColor: color }}
      />
    </div>
  </div>
);

const Indicator: React.FC<{
  label: string;
  value: string;
  detail: string;
}> = ({ label, value, detail }) => (
  <div>
    <p className="font-bold">{label}</p>
    <p className="mt-4">{value}</p>
    <p className="mt-4 font-bold">{detail}</p>
  </div>
);

const CHART_METRICS = [
  { key: "ipm", label: "IPM", color: "#2563eb", get: (m: MetricSnapshot) => m.ipmAvg },
  { key: "idm", label: "IDM", color: "#16a34a", get: (m: MetricSnapshot) => m.idmAvg },
  {
    key: "wpm",
    label: "P/min",
    color: "#dc2626",
    get: (m: MetricSnapshot) => m.wordsPerMinute,
  },
  {
    key: "dissonance",
    label: "Disso.",
    color: "#9333ea",
    get: (m: MetricSnapshot) => m.dissonanceCount,
  },
  {
    key: "subharmonic",
    label: "Sub-H",
    color: "#ea580c",
    get: (m: MetricSnapshot) => m.subharmonic5_12 || 0,
  },
];

const PatientEvolutionChart: React.FC<{ reports: SessionReportRecord[] }> = ({
  reports,
}) => {
  const ordered = [...reports]
    .sort(
      (a, b) =>
        new Date(a.createdAt || 0).getTime() -
        new Date(b.createdAt || 0).getTime(),
    )
    .slice(-20);
  const width = 980;
  const height = 260;
  const padX = 46;
  const padY = 24;
  const chartWidth = width - padX * 2;
  const chartHeight = height - padY * 2;

  const xFor = (index: number) =>
    padX + (ordered.length <= 1 ? chartWidth / 2 : (index / (ordered.length - 1)) * chartWidth);

  const pointsFor = (metric: (typeof CHART_METRICS)[number]) => {
    const values = ordered.map((report) => Number(metric.get(report.sessionAverage) || 0));
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 1);
    const span = max - min || 1;
    return values
      .map((value, index) => {
        const x = xFor(index);
        const y = padY + chartHeight - ((value - min) / span) * chartHeight;
        return `${x},${y}`;
      })
      .join(" ");
  };

  if (!ordered.length) {
    return (
      <div className="mt-3 border border-black p-4 text-xs">
        Sem sessoes suficientes para desenhar evolucao longitudinal.
      </div>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto border border-black p-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[760px] w-full">
        {[0, 1, 2, 3, 4].map((line) => {
          const y = padY + (line / 4) * chartHeight;
          const isCenter = line === 2;
          return (
            <line
              key={line}
              x1={padX}
              x2={width - padX}
              y1={y}
              y2={y}
              stroke={isCenter ? "#94a3b8" : "#d1d5db"}
              strokeDasharray={isCenter ? "0" : "5 5"}
              strokeWidth={isCenter ? "1.4" : "1"}
            />
          );
        })}
        {ordered.map((report, index) => {
          const x = xFor(index);
          return (
            <g key={report.sessionId}>
              <line
                x1={x}
                x2={x}
                y1={padY}
                y2={height - padY}
                stroke="#e5e7eb"
                strokeWidth="1"
              />
              <text
                x={x}
                y={height - 4}
                textAnchor="middle"
                fontSize="10"
                fill="#111827"
              >
                {reportEndDate(report).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                })}
              </text>
            </g>
          );
        })}
        {CHART_METRICS.map((metric) => (
          <polyline
            key={metric.key}
            points={pointsFor(metric)}
            fill="none"
            stroke={metric.color}
            strokeWidth="3"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] font-bold">
        {CHART_METRICS.map((metric) => (
          <span key={metric.key} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2 w-5"
              style={{ backgroundColor: metric.color }}
            />
            {metric.label}
          </span>
        ))}
      </div>
    </div>
  );
};
