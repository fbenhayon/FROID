import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
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
  splitSessionResult,
  shortId,
} from "../lib/patient-dashboard";
import {
  formatDuration,
  loadSessionReports,
  MetricSnapshot,
  saveSessionReport,
  SessionReportRecord,
} from "../lib/session-report";
import { dashboardText, loadSessionLanguagePreferences, normalizeSessionLocale } from "../lib/localization";

type PatientFollowStatus = "active" | "inactive";

const PATIENT_STATUS_STORAGE_KEY = "froid_patient_follow_status_v1";

function loadPatientStatuses(): Record<string, PatientFollowStatus> {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(PATIENT_STATUS_STORAGE_KEY) || "{}",
    );
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function savePatientStatuses(statuses: Record<string, PatientFollowStatus>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PATIENT_STATUS_STORAGE_KEY, JSON.stringify(statuses));
}

export const PatientDetail: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { patientKey = "" } = useParams<{ patientKey: string }>();
  const requestedReturnTo = (location.state as { returnTo?: string } | null)?.returnTo;
  const returnTo = requestedReturnTo === "/dashboard/resumido"
    ? "/dashboard/resumido"
    : "/dashboard";
  const decodedPatientKey = decodeURIComponent(patientKey);
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );
  const [patientStatuses, setPatientStatuses] = useState<
    Record<string, PatientFollowStatus>
  >(() => loadPatientStatuses());
  const [professionalObservation, setProfessionalObservation] = useState("");
  const [observationSaving, setObservationSaving] = useState(false);
  const [observationFeedback, setObservationFeedback] = useState("");

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("froid_token") || "";
    fetch(apiUrl("/api/session-reports"), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
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
  const locale = normalizeSessionLocale(
    group?.latestReport.reportLocale,
    loadSessionLanguagePreferences().reportLocale,
  );
  const tr = (text: string) => dashboardText(locale, text);

  if (!group) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-300">
        <div className="max-w-md rounded-lg border border-slate-800 bg-slate-900 p-6 text-center shadow-sm">
          <h1 className="text-lg font-bold text-slate-100">
            {tr("Paciente não encontrado")}
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Ainda não há relatórios locais ou sincronizados para este paciente.
          </p>
          <button
            onClick={() => navigate("/dashboard")}
            className="mt-4 rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800"
          >
            {tr("Voltar ao dashboard")}
          </button>
        </div>
      </div>
    );
  }

  const latest = group.latestReport;
  const patientStatus = patientStatuses[decodedPatientKey] || "active";
  const patientIsActive = patientStatus === "active";
  const activePatients = patientIsActive ? 1 : 0;
  const inactivePatients = patientIsActive ? 0 : 1;
  const patientStatusLabel = patientIsActive ? "Paciente ativo" : "Paciente inativo";
  const updatePatientStatus = (status: PatientFollowStatus) => {
    setPatientStatuses((current) => {
      const next = { ...current, [decodedPatientKey]: status };
      savePatientStatuses(next);
      return next;
    });
  };
  const saveProfessionalObservation = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = professionalObservation.trim();
    if (!text) return;
    setObservationSaving(true);
    setObservationFeedback("");
    try {
      const token = localStorage.getItem("froid_token") || "";
      const response = await fetch(
        apiUrl(`/api/session-reports/${latest.sessionId}/clinical-notes`),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ text }),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível salvar a observação.");
      }
      const updatedReport = {
        ...latest,
        clinicalNotes: [...(latest.clinicalNotes || []), data.note],
      };
      saveSessionReport(updatedReport);
      setReports((current) =>
        current.map((report) =>
          report.sessionId === updatedReport.sessionId ? updatedReport : report,
        ),
      );
      setProfessionalObservation("");
      setObservationFeedback("Observação registrada no prontuário longitudinal.");
    } catch (err) {
      setObservationFeedback(
        err instanceof Error ? err.message : "Falha ao salvar observação.",
      );
    } finally {
      setObservationSaving(false);
    }
  };
  const context = {
    patient: group.patient,
    patient_summary: {
      total_sessions: group.totalSessions,
      completed_sessions: group.completedSessions,
      active_sessions: group.activeSessions,
      active_patient: patientIsActive,
      follow_status: patientStatus,
      total_analyses: group.totalAnalyses,
      dominant_zone: group.dominantZone,
      recurrent_emotion: group.recurrentEmotion,
      dissonance_events: group.dissonanceCount,
      clinical_note: group.clinicalNote,
    },
    latest_report_baseline: latest.baseline,
    latest_report_average: latest.sessionAverage,
    latest_report_cuts: latest.tenMinuteCuts,
  };
  const signal = patientAdvancedSignal(group);
  const sessionTableColSpan = patientMetricRows(latest.sessionAverage).length + 4;
  const resultTextColSpan = Math.max(1, sessionTableColSpan - 2);
  const latestResultLines = splitSessionResult(latest);
  const latestCutCount = latest.tenMinuteCuts.filter((cut) => cut.sampleCount > 0).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              {tr("Dashboard Longitudinal do Paciente")}
            </p>
            <h1 className="text-xl font-bold text-slate-100">
              {group.patient.name || tr("Paciente sem nome")}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              ID: {group.patient.document || tr("Não informado")} | Última sessão{" "}
              {formatDateTime(reportEndDate(latest))}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <span
              className="rounded border border-blue-800 bg-blue-950 px-3 py-2 text-xs font-black text-blue-200"
              title="Indicador calculado de prioridade atual do acompanhamento"
            >
              {tr("Prioridade")}: {signal.priority}
            </span>
            <button
              onClick={() => navigate(`/session/${latest.sessionId}`)}
              className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800"
            >
              Abrir sessão
            </button>
            <button
              onClick={() => navigate(returnTo)}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
            >
              {tr("Voltar")}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl items-start gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-3">
          <section className="rounded-lg border border-blue-800 bg-blue-950 p-3">
            <div className="mb-3">
              <h2 className="text-sm font-bold text-blue-100">
                Linha comparativa da última sessão
              </h2>
            </div>
            <div className="grid gap-2 md:grid-cols-5">
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IPM baseline
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(latest.baseline.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IPM medio
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(latest.sessionAverage.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IDM baseline
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(latest.baseline.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IDM medio
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(latest.sessionAverage.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  Estado
                </p>
                <p className="text-sm font-bold text-blue-100">
                  {signal.state}
                </p>
              </div>
            </div>
          </section>

          <PatientMetricTable
            title="Parâmetros iniciais - 60 segundos"
            rows={[{ label: latest.baseline.label, metrics: patientMetricRows(latest.baseline) }]}
          />

          <PatientMetricTable
            title="Média das métricas da última sessão"
            rows={[{ label: latest.sessionAverage.label, metrics: patientMetricRows(latest.sessionAverage) }]}
          />

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-100">
                  Evolução das últimas 20 sessões
                </h2>
                <p className="mt-1 text-[11px] text-slate-400">
                  IPM, IDM, palavras por minuto, dissonâncias e sub-harmônicos em escala própria.
                </p>
              </div>
              <span className="rounded bg-slate-950 px-2 py-1 text-[10px] font-black uppercase text-slate-400">
                {signal.state}
              </span>
            </div>
            <PatientEvolutionChart reports={group.reports} />
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">Indicadores Clínicos</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <Indicator
                label="Zona FROID Dominante"
                value={group.dominantZone ? `Zona ${group.dominantZone}` : "--"}
                detail={`Baseado em ${group.completedSessions} sessões`}
              />
              <Indicator
                label="Emoção Recorrente"
                value={group.recurrentEmotion || "--"}
                detail="FACS - Análise Facial"
              />
              <Indicator
                label="Dissonâncias"
                value={String(group.dissonanceCount)}
                detail="Eventos facial-vocal confirmados"
              />
            </div>
            <div className="mt-4 rounded-lg border border-amber-600 bg-amber-950/40 px-3 py-3">
              <p className="text-[11px] font-black uppercase tracking-wide text-amber-100">
                Nota Clínica
              </p>
              <p className="mt-1 text-sm font-semibold leading-relaxed text-amber-100">
                {group.clinicalNote}
              </p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-5">
              <PatientScoreBar label="Carga de sinal" value={signal.signalLoad} color="#f97316" />
              <PatientScoreBar label="Comunicação" value={signal.communication} color="#0ea5e9" />
              <PatientScoreBar label="Continuidade" value={signal.continuity} color="#22c55e" />
              <PatientScoreBar label="Insight" value={signal.insight} color="#8b5cf6" />
              <PatientScoreBar label="Qualidade" value={signal.dataQuality} color="#14b8a6" />
            </div>
            <p className="mt-3 rounded-lg border border-blue-800 bg-blue-950 px-3 py-2 text-xs font-semibold text-blue-100">
              Linha comparativa: IPM {fmt(latest.baseline.ipmAvg, 1)} -&gt;{" "}
              {fmt(latest.sessionAverage.ipmAvg, 1)} (
              {fmtDelta(latest.sessionAverage.ipmAvg - latest.baseline.ipmAvg, 1)})
              {" | "}IDM {fmt(latest.baseline.idmAvg, 2)} -&gt;{" "}
              {fmt(latest.sessionAverage.idmAvg, 2)}
            </p>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">Sessões realizadas</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-max table-auto text-left text-[10px] leading-tight">
                <thead className="text-[9px] uppercase tracking-normal text-slate-400">
                  <tr>
                    <th className="whitespace-nowrap py-1 pr-2">Data</th>
                    <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                      Sessão
                    </th>
                    {patientMetricRows(latest.sessionAverage).map(([label]) => (
                      <th
                        key={label}
                        className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold"
                      >
                        {label}
                      </th>
                    ))}
                    <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                      Pagamento
                    </th>
                    <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                      Detalhe
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {group.reports.map((report) => {
                    const resultLines = splitSessionResult(report);
                    return (
                      <React.Fragment key={report.sessionId}>
                        <tr className="align-top">
                          <td className="whitespace-nowrap py-1 pr-2 font-bold text-slate-300">
                            {formatDateTime(reportEndDate(report))}
                          </td>
                          <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">
                            {shortId(report.sessionId)}
                          </td>
                          {patientMetricRows(report.sessionAverage).map(([label, value]) => (
                            <td
                              key={`${report.sessionId}-${label}`}
                              className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300"
                              title={value}
                            >
                              {value}
                            </td>
                          ))}
                          <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-slate-300">
                            {paymentStatusForReport(report)}
                          </td>
                          <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                            <button
                              onClick={() =>
                                navigate(`/session/${report.sessionId}/report`)
                              }
                              className="rounded border border-slate-700 bg-slate-950 px-2 py-1 font-bold text-slate-300 hover:bg-slate-800"
                            >
                              Ver
                            </button>
                          </td>
                        </tr>
                        <tr className="bg-blue-950/70 align-top">
                          <td className="border-r border-blue-800 px-2 py-2 text-[10px] font-black uppercase text-blue-200">
                            Resultado
                          </td>
                          <td className="border-r border-blue-800 px-2 py-2 text-[10px] font-bold text-blue-200">
                            {shortId(report.sessionId)}
                          </td>
                          <td colSpan={resultTextColSpan} className="px-2 py-2 text-xs leading-relaxed text-blue-100">
                            {resultLines[0]}
                          </td>
                        </tr>
                        <tr className="border-b border-slate-700 bg-slate-950 align-top">
                          <td className="border-r border-slate-700 px-2 py-2 text-[10px] font-black uppercase text-slate-400">
                            Complemento
                          </td>
                          <td className="border-r border-slate-700 px-2 py-2 text-[10px] font-bold text-slate-400">
                            Análise
                          </td>
                          <td colSpan={resultTextColSpan} className="px-2 py-2 text-xs leading-relaxed text-slate-300">
                            {resultLines[1] || "Complemento ainda não consolidado."}
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">{tr("Histórico de Sessões")}</h2>
            <table className="mt-3 w-full table-fixed text-left text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                <tr className="border-b border-slate-700">
                  <th className="w-[13%]">ID</th>
                  <th className="w-[12%]">STATUS</th>
                  <th className="w-[23%]">INICIO</th>
                  <th className="w-[23%]">FIM</th>
                  <th className="w-[17%]">DURACAO</th>
                  <th>ANALISES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
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
                    <td>{index === 0 ? "Concluída" : "Ativa"}</td>
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
        </div>

        <aside className="space-y-3 lg:sticky lg:top-3 lg:max-h-[calc(100vh-1.5rem)] lg:overflow-y-auto">
          <section className="rounded-lg border border-blue-800 bg-blue-950 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-blue-100">{tr("Resumo do paciente")}</h2>
              <span className="rounded bg-slate-950 px-2 py-1 text-[10px] font-black uppercase text-blue-200">
                {signal.state}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <PatientKpi label={tr("Total de Sessões")} value={String(group.totalSessions)} />
              <PatientKpi label={tr("Inativas")} value={String(inactivePatients)} />
              <PatientKpi label={tr("Ativas")} value={String(activePatients)} tone="green" />
              <PatientKpi label={tr("Análises")} value={String(group.totalAnalyses)} />
              <PatientKpi label={tr("Atenção")} value={`${Math.round(signal.attentionIndex)}/100`} tone="red" />
              <PatientKpi label={tr("Qualidade")} value={signal.qualityLabel} tone="green" />
              <PatientKpi label={tr("Comunicação")} value={`${Math.round(signal.communication)}/100`} tone="blue" />
              <PatientKpi label="Insight" value={`${Math.round(signal.insight)}/100`} tone="violet" />
            </div>
            <div className="mt-2 rounded border border-blue-100 bg-slate-950 p-2">
              <p className="text-[9px] font-black uppercase tracking-wide text-blue-300">
                {tr("Status definido pelo profissional")}
              </p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => updatePatientStatus("active")}
                  className={`rounded border px-2 py-1.5 text-[10px] font-black uppercase ${
                    patientIsActive
                      ? "border-emerald-700 bg-emerald-950/40 text-emerald-200"
                      : "border-slate-700 bg-slate-950 text-slate-400 hover:bg-slate-100"
                  }`}
                >
                  {tr("Ativo")}
                </button>
                <button
                  type="button"
                  onClick={() => updatePatientStatus("inactive")}
                  className={`rounded border px-2 py-1.5 text-[10px] font-black uppercase ${
                    !patientIsActive
                      ? "border-amber-600 bg-amber-950/40 text-amber-100"
                      : "border-slate-700 bg-slate-950 text-slate-400 hover:bg-slate-100"
                  }`}
                >
                  {tr("Inativo")}
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">{tr("Painel de acompanhamento")}</h2>
            <p className="mt-1 text-[11px] text-slate-400">
              Leitura operacional para orientar a próxima decisão clínica deste paciente.
            </p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <SideMetric label={tr("Prioridade")} value={signal.priority} tone="blue" />
              <SideMetric label={tr("Status")} value={patientStatusLabel} tone={patientIsActive ? "green" : "amber"} />
              <SideMetric label={tr("Estado clínico")} value={signal.state} />
              <SideMetric label={tr("Ação sugerida")} value={signal.action} tone="amber" wide />
              <SideMetric label={tr("Qualidade")} value={signal.qualityLabel} tone="green" />
              <SideMetric label="IPM tendência" value={fmtDelta(signal.ipmTrend, 1)} />
              <SideMetric label="IDM recente" value={fmt(signal.idmRecent, 2)} />
            </div>
          </section>

          <section className="min-h-[360px] rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-100">FROID Explica</h2>
                <p className="mt-1 text-[11px] text-slate-400">
                  Consulta longitudinal fixa para este paciente.
                </p>
              </div>
              <button
                onClick={() => navigate("/settings")}
                className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-bold text-slate-300 hover:bg-slate-100"
              >
                Meus Prompts...
              </button>
            </div>
            <AIInsights
              zones={latest.sessionAverage.zones || []}
              ipmScore={latest.sessionAverage.ipmAvg}
              coherenceStatus={latest.sessionAverage.coherenceStatus}
              baselineEstablished
              sessionId={latest.sessionId}
              responseLocale={locale}
              extraContext={context}
              controlsSticky
              messagesClassName="min-h-[190px]"
            />
          </section>

          <form
            onSubmit={saveProfessionalObservation}
            className="rounded-lg border border-emerald-900 bg-slate-900 p-3"
          >
            <h2 className="text-sm font-bold text-slate-100">
              {tr("Observações do profissional")}
            </h2>
            <p className="mt-1 text-[11px] leading-5 text-slate-400">
              Registre uma observação vinculada à sessão mais recente e ao
              histórico longitudinal deste paciente.
            </p>
            <textarea
              value={professionalObservation}
              onChange={(event) => setProfessionalObservation(event.target.value)}
              maxLength={4000}
              rows={4}
              placeholder="Escreva a observação clínica..."
              className="mt-3 w-full resize-y rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none focus:border-emerald-500"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-[10px] text-slate-400">
                {professionalObservation.length}/4000 caracteres
              </span>
              <button
                type="submit"
                disabled={observationSaving || !professionalObservation.trim()}
                className="rounded bg-emerald-700 px-3 py-2 text-[11px] font-black text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {observationSaving ? tr("Salvando...") : tr("Salvar observação")}
              </button>
            </div>
            {observationFeedback && (
              <p className="mt-2 text-[11px] font-semibold text-emerald-200">
                {observationFeedback}
              </p>
            )}
            {!!latest.clinicalNotes.length && (
              <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                {latest.clinicalNotes.slice(-3).reverse().map((note) => (
                  <article key={note.id} className="rounded bg-slate-950 p-2 text-xs text-slate-300">
                    <p>{note.text}</p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {formatDateTime(new Date(note.timestamp))}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </form>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">{tr("Resumo longitudinal")}</h2>
            <div className="mt-2 space-y-1.5 text-xs text-slate-300">
              <p>
                <strong>Nota clinica:</strong> {group.clinicalNote}
              </p>
              <p>
                <strong>Dissonancias:</strong> {group.dissonanceCount} evento(s) confirmado(s)
              </p>
              <p>
                <strong>Predominancia:</strong>{" "}
                {group.dominantZone ? `Zona ${group.dominantZone}` : "--"} |{" "}
                {group.recurrentEmotion || "--"}
              </p>
              <p>
                <strong>Última sessão:</strong>{" "}
                {formatDateTime(reportEndDate(latest))} |{" "}
                {formatDuration(latest.durationSeconds)} | {latestCutCount} cortes
              </p>
              <p>
                <strong>Pagamento:</strong> {paymentStatusForReport(latest)}
              </p>
              <p>
                <strong>Observações:</strong> {latest.clinicalNotes.length} anotações |{" "}
                {latest.dissonances.length} dissonâncias
              </p>
            </div>
          </section>

          <section className="rounded-lg border border-blue-800 bg-blue-950 p-3">
            <h2 className="text-sm font-bold text-blue-100">{tr("Resultado mais recente")}</h2>
            <p className="mt-2 text-xs leading-relaxed text-blue-100">
              {latestResultLines[0]}
            </p>
            {latestResultLines[1] && (
              <p className="mt-2 text-xs leading-relaxed text-blue-100">
                {latestResultLines[1]}
              </p>
            )}
            <button
              onClick={() => navigate(`/session/${latest.sessionId}/report`)}
              className="mt-3 rounded border border-blue-800 bg-slate-950 px-3 py-2 text-[10px] font-bold text-blue-200 hover:bg-blue-900"
            >
              {tr("Abrir relatório da última sessão")}
            </button>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <h2 className="text-sm font-bold text-slate-100">{tr("Indicadores de seguimento")}</h2>
            <div className="mt-2 space-y-2">
              <PatientScoreBar label="Carga de sinal" value={signal.signalLoad} color="#f97316" />
              <PatientScoreBar label="Comunicação" value={signal.communication} color="#0ea5e9" />
              <PatientScoreBar label="Continuidade" value={signal.continuity} color="#22c55e" />
              <PatientScoreBar label="Insight" value={signal.insight} color="#8b5cf6" />
              <PatientScoreBar label="Qualidade" value={signal.dataQuality} color="#14b8a6" />
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
};

const SideMetric: React.FC<{
  label: string;
  value: string;
  tone?: "blue" | "green" | "amber";
  wide?: boolean;
}> = ({ label, value, tone = "blue", wide = false }) => {
  const valueClass =
    tone === "green"
      ? "text-emerald-200"
      : tone === "amber"
        ? "text-amber-100"
        : "text-blue-100";
  return (
    <div
      className={`rounded border border-slate-700 bg-slate-950 p-2 ${
        wide ? "col-span-2" : ""
      }`}
    >
      <p className="text-[9px] font-bold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className={`mt-1 text-xs font-black ${valueClass}`}>{value}</p>
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
      ? "text-emerald-200"
      : tone === "red"
        ? "text-red-700"
        : tone === "violet"
          ? "text-violet-700"
          : "text-blue-100";
  return (
    <div className="rounded border border-blue-100 bg-slate-950 px-3 py-2">
      <p className="text-[9px] font-black uppercase tracking-widest text-blue-300">
        {label}
      </p>
      <p className={`mt-1 text-lg font-black ${color}`}>{value}</p>
    </div>
  );
};

const PatientScoreBar: React.FC<{
  label: string;
  value: number;
  color: string;
}> = ({ label, value, color }) => (
  <div>
    <div className="mb-1 flex items-center justify-between gap-2 text-[10px] font-bold uppercase text-slate-400">
      <span>{label}</span>
      <span>{Math.round(value)}/100</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
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
  <div className="rounded border border-slate-700 bg-slate-950 p-3">
    <p className="text-[10px] font-bold uppercase text-slate-400">{label}</p>
    <p className="mt-2 text-sm font-black text-slate-100">{value}</p>
    <p className="mt-2 text-[11px] font-semibold text-slate-400">{detail}</p>
  </div>
);

function patientMetricRows(snapshot: MetricSnapshot) {
  return [
    ["IPM", fmt(snapshot.ipmAvg, 1)],
    ["IDM", fmt(snapshot.idmAvg, 2)],
    ["ZONAS", snapshot.dominantZone ? `Zona ${snapshot.dominantZone}` : "--"],
    ["Tom", snapshot.emotionalTone || "--"],
    ["P/min", fmt(snapshot.wordsPerMinute, 1)],
    ["Disso.", String(snapshot.dissonanceCount || 0)],
    ["MFCC7", fmt(snapshot.mfcc7, 3)],
    ["MFCC9", fmt(snapshot.mfcc9, 3)],
    ["DMFCC7", fmt(snapshot.mfcc7Delta, 4)],
    ["DDMFCC9", fmt(snapshot.mfcc9DeltaDelta, 4)],
    ["F0 Med.", fmt(snapshot.f0Mean, 2)],
    ["ZCR", fmt(snapshot.zcr, 3)],
    ["Jitter idx.", fmt(snapshot.jitter, 3)],
    ["Shimmer idx.", fmt(snapshot.shimmer, 3)],
    ["Beta 12-30Hz", fmt(snapshot.spectralBeta12_30, 3)],
    ["Gama 30-80Hz", fmt(snapshot.spectralGamma30_80, 3)],
    ["Ind. espectral", fmt(snapshot.spectralBandIndex, 3)],
    ["Sub-H 5-12Hz", fmt(snapshot.subharmonic5_12, 3)],
    ["Sub-H 12-20Hz", fmt(snapshot.subharmonic12_20, 3)],
  ];
}

const PatientMetricTable: React.FC<{
  title: string;
  rows: Array<{ label: string; metrics: string[][] }>;
}> = ({ title, rows }) => (
  <section className="rounded-lg border border-slate-800 bg-slate-900 p-3">
    <div className="mb-3">
      <h2 className="text-sm font-bold text-slate-100">{title}</h2>
    </div>
    <div className="overflow-x-auto">
      <table className="min-w-max table-auto text-left text-[10px] leading-tight">
        <thead className="text-[9px] uppercase tracking-normal text-slate-400">
          <tr>
            <th className="whitespace-nowrap py-1 pr-2">Corte</th>
            {rows[0]?.metrics.map(([label]) => (
              <th
                key={label}
                className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((row) => (
            <tr key={row.label} className="align-top">
              <td className="whitespace-nowrap py-1 pr-2 font-bold text-slate-300">
                {row.label}
              </td>
              {row.metrics.map(([label, value]) => (
                <td
                  key={`${row.label}-${label}`}
                  className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300"
                  title={value}
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
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
      <div className="mt-3 rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-400">
        Sem sessões suficientes para desenhar evolução longitudinal.
      </div>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto rounded border border-slate-700 bg-slate-950 p-2">
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

