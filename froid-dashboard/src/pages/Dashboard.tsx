import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  fmtDelta,
  formatDateTime,
  limitWords,
  mergeReports,
  paymentStatusForReport,
  reportEndDate,
  sessionMetricCells,
  sessionResultText,
  shortId,
} from "../lib/patient-dashboard";
import {
  loadSessionReports,
  rememberSessionPatient,
  SessionReportRecord,
} from "../lib/session-report";

interface DashboardProps {
  user?: any;
  onLogout?: () => void;
}

interface SessionEvent {
  id: number;
  type: "invite_created" | "invite_opened" | "invite_accepted" | "patient_joined";
  session_id: string;
  patient_name?: string;
  created_at: string;
}

function makeId() {
  return `froid-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export const Dashboard: React.FC<DashboardProps> = ({ user, onLogout }) => {
  const nav = useNavigate();
  const [patientActivity, setPatientActivity] = useState("");
  const [selectedPatientKey, setSelectedPatientKey] = useState("");
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const professionalName = user?.name || user?.email || "Profissional";

  useEffect(() => {
    setReports(loadSessionReports());
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

  const patientGroups = useMemo(() => buildPatientGroups(reports), [reports]);
  const selectedGroup =
    patientGroups.find((group) => group.key === selectedPatientKey) ||
    patientGroups[0];
  const openPatientRegistration = (
    patient?: {
      name?: string;
      email?: string;
      phone?: string;
    },
    patientKey?: string,
  ) => {
    if (patientKey) setSelectedPatientKey(patientKey);
    const params = new URLSearchParams();
    if (patient?.name) params.set("name", patient.name);
    if (patient?.email) params.set("email", patient.email);
    if (patient?.phone) params.set("phone", patient.phone);
    const query = params.toString();
    nav(`/patients/new${query ? `?${query}` : ""}`);
  };

  useEffect(() => {
    let active = true;

    const pollSessionEvents = async () => {
      try {
        if (eventCursorRef.current === null) {
          const response = await fetch(apiUrl("/api/session-events/latest"));
          if (!response.ok) return;
          const data = await response.json();
          eventCursorRef.current = Number(data?.latest_id || 0);
          return;
        }

        const response = await fetch(
          apiUrl(`/api/session-events?after=${eventCursorRef.current}`),
        );
        if (!response.ok) return;
        const data = await response.json();
        const events: SessionEvent[] = Array.isArray(data?.events)
          ? data.events
          : [];
        eventCursorRef.current = Math.max(
          Number(eventCursorRef.current || 0),
          Number(data?.latest_id || 0),
          ...events.map((event) => Number(event.id || 0)),
        );
        const visibleEvents = events.filter((event) =>
          ["invite_opened", "invite_accepted", "patient_joined"].includes(
            event.type,
          ),
        );
        const latest = visibleEvents[visibleEvents.length - 1];
        if (!latest || !active) return;
        const patient = latest.patient_name || "Paciente";
        if (latest.type === "invite_opened") {
          setPatientActivity(`${patient} abriu o convite FROID.`);
        }
        if (latest.type === "invite_accepted") {
          setPatientActivity(`${patient} confirmou cadastro e consentimentos LGPD.`);
        }
        if (
          latest.type === "patient_joined" &&
          latest.session_id &&
          !redirectingRef.current
        ) {
          setPatientActivity(`${patient} entrou na sessao. Abrindo sala profissional...`);
          rememberSessionPatient(latest.session_id, { name: patient });
          redirectingRef.current = true;
          window.setTimeout(() => {
            if (active) nav(`/session/${latest.session_id}`);
          }, 900);
        }
      } catch {
        // Polling best-effort.
      }
    };

    void pollSessionEvents();
    const intervalId = window.setInterval(pollSessionEvents, 3000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [nav]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-600">
              Dashboard Profissional
            </p>
            <h1 className="text-xl font-bold text-slate-900">FROID Dashboard</h1>
            <p className="mt-1 text-xs text-slate-500">
              Bem-vindo, {professionalName}
            </p>
          </div>
          <button
            onClick={onLogout}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
          >
            Sair
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 p-6">

      {patientActivity && (
        <p className="rounded-lg border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs font-bold text-cyan-900">
          {patientActivity}
        </p>
      )}

      {selectedGroup && (
        <p className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-900">
          Aviso de agenda: acesse o layout de{" "}
          {selectedGroup.patient.name || "Paciente sem nome"} e envie o convite da
          sessao quando estiver a 5 minutos do atendimento programado.
        </p>
      )}

      <section className="rounded-lg border border-blue-100 bg-blue-50 p-4">
        <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-blue-950">Meus Pacientes</h2>
          <p className="mt-1 text-[11px] text-blue-700">
            Ultimas sessoes, metricas medias e resultado clinico resumido.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button
            onClick={() => openPatientRegistration()}
            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
          >
            + Novo Paciente
          </button>
          <button
            onClick={() => nav(`/session/${makeId()}`)}
            className="rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-700 hover:bg-blue-50"
          >
            + Nova Sessao Direta
          </button>
        </div>
        </div>
      </section>

      {selectedGroup && (
        <section className="sticky top-0 z-20 rounded-lg border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
          <h2 className="mb-2 text-sm font-bold text-slate-900">FROID Explica</h2>
          <div className="max-h-56 overflow-y-auto pr-1">
            <AIInsights
              zones={selectedGroup.latestReport.sessionAverage.zones || []}
              ipmScore={selectedGroup.latestReport.sessionAverage.ipmAvg}
              coherenceStatus={
                selectedGroup.latestReport.sessionAverage.coherenceStatus
              }
              baselineEstablished
              sessionId={selectedGroup.latestReport.sessionId}
              extraContext={{
                patient: selectedGroup.patient,
                latest_report_average: selectedGroup.latestReport.sessionAverage,
                latest_report_baseline: selectedGroup.latestReport.baseline,
                last_three_sessions: selectedGroup.reports.slice(0, 3).map((report) => ({
                  session_id: report.sessionId,
                  average: report.sessionAverage,
                  result: sessionResultText(report, 120),
                  payment_status: paymentStatusForReport(report),
                })),
              }}
            />
          </div>
        </section>
      )}

      <section className="space-y-4">
        {patientGroups.length === 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-500">
            Nenhum paciente com relatorio encontrado. Finalize uma sessao para
            alimentar o dashboard profissional.
          </div>
        )}

        {patientGroups.map((group) => (
          <article
            key={group.key}
            className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            onMouseEnter={() => setSelectedPatientKey(group.key)}
          >
            <div className="flex justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  {group.patient.name || "Paciente sem nome"}
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  CPF: {group.patient.document || "Nao informado"}
                </p>
              </div>
              <div className="flex h-fit flex-wrap justify-end gap-2">
                <button
                  onClick={() =>
                    openPatientRegistration(
                      {
                        name: group.patient.name,
                        email: group.patient.email,
                        phone: group.patient.phone,
                      },
                      group.key,
                    )
                  }
                  className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
                >
                  Convite
                </button>
                <button
                  onClick={() => {
                    setSelectedPatientKey(group.key);
                    nav(`/patients/${encodeURIComponent(group.key)}`);
                  }}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
                >
                  Ver Detalhes
                </button>
              </div>
            </div>

            <div className="mt-4">
              <p className="text-xs font-bold text-slate-900">Ultimas 3 Sessoes</p>
              <div className="mt-3 space-y-3">
                {group.reports.slice(0, 3).map((report, index) => (
                  <div
                    key={report.sessionId}
                    className="rounded-lg border border-slate-100 bg-slate-50/60 p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-bold text-slate-900">
                          {index === 0 ? "Concluida " : "Ativa "}
                          {shortId(report.sessionId)}
                        </p>
                        <p className="mt-0.5 text-[10px] font-semibold text-slate-500">
                          {formatDateTime(reportEndDate(report))}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <span className="rounded bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
                          {paymentStatusForReport(report)}
                        </span>
                        <button
                          onClick={() => nav(`/session/${report.sessionId}/report`)}
                          className="rounded border border-slate-200 bg-white px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                        >
                          Ver
                        </button>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8 xl:grid-cols-12">
                      {sessionMetricCells(report.sessionAverage).map((cell) => (
                        <div
                          key={cell.key}
                          className="min-w-0 rounded border border-slate-100 bg-white px-2 py-1.5"
                        >
                          <p className="truncate text-[9px] font-bold uppercase tracking-wide text-slate-400">
                            {cell.label}
                          </p>
                          <p className="mt-0.5 truncate text-[11px] font-semibold text-slate-800">
                            {cell.value}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-3 rounded border border-blue-50 bg-white px-3 py-2 text-xs leading-relaxed text-slate-600">
                      <strong className="text-slate-800">Resultado da sessao:</strong>{" "}
                      {sessionResultText(report, 85)}
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-3 rounded border border-blue-100 bg-blue-50 px-3 py-2 text-[11px] font-medium text-blue-900">
                Linha comparativa mais recente: IPM{" "}
                {fmt(group.latestReport.baseline.ipmAvg, 1)} -&gt;{" "}
                {fmt(group.latestReport.sessionAverage.ipmAvg, 1)} (
                {fmtDelta(
                  group.latestReport.sessionAverage.ipmAvg -
                    group.latestReport.baseline.ipmAvg,
                  1,
                )}
                ) | IDM {fmt(group.latestReport.baseline.idmAvg, 2)} -&gt;{" "}
                {fmt(group.latestReport.sessionAverage.idmAvg, 2)} | Tema{" "}
                {limitWords(
                  group.latestReport.sessionAverage.theme ||
                    group.latestReport.baseline.theme,
                  6,
                )}
              </p>
            </div>
          </article>
        ))}
      </section>

      </main>
    </div>
  );
};
