import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { AIInsights } from "../components/panels/AIInsights";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  mergeReports,
  patientAdvancedSignal,
  professionalPortfolioSummary,
} from "../lib/patient-dashboard";
import { loadSessionReports, SessionReportRecord } from "../lib/session-report";

type Props = { user?: FroidUser | null; onLogout?: () => void };
type FinancialSummary = {
  total_due_brl?: string;
  total_received_brl?: string;
  total_pending_brl?: string;
};

function mean(reports: SessionReportRecord[], select: (report: SessionReportRecord) => number | null | undefined) {
  const values = reports.map(select).filter((value): value is number => Number.isFinite(value));
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

export const ProfessionalDashboardSummary: React.FC<Props> = ({ user, onLogout }) => {
  const nav = useNavigate();
  const [reports, setReports] = useState<SessionReportRecord[]>(() => loadSessionReports());
  const [financial, setFinancial] = useState<FinancialSummary | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const token = localStorage.getItem("froid_token") || "";
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(apiUrl("/api/session-reports"), { headers }).then((response) =>
        response.ok ? response.json() : null,
      ),
      fetch(apiUrl("/api/professional/receivables"), { headers }).then((response) =>
        response.ok ? response.json() : null,
      ),
    ]).then(([reportData, receivableData]) => {
      if (!active) return;
      const remote = Array.isArray(reportData?.reports) ? reportData.reports : [];
      if (remote.length) setReports((current) => mergeReports(current, remote));
      setFinancial(receivableData?.summary || null);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const groups = useMemo(() => buildPatientGroups(reports), [reports]);
  const portfolio = useMemo(() => professionalPortfolioSummary(groups), [groups]);
  const selected = groups.find((group) => group.key === selectedKey) || groups[0];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              Dashboard Profissional Resumido
            </p>
            <h1 className="mt-1 text-xl font-bold">{user?.name || user?.email || "Profissional"}</h1>
          </div>
          <div className="flex gap-2">
            <button onClick={() => nav("/dashboard")} className="rounded border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100">Dashboard detalhado</button>
            <button onClick={() => nav("/settings")} className="rounded border border-slate-700 px-3 py-2 text-xs font-bold">Administrativo</button>
            <button onClick={onLogout} className="rounded border border-slate-700 px-3 py-2 text-xs font-bold">Sair</button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 p-5">
        <section className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="flex min-w-max items-center gap-5 text-[11px]">
            <strong className="text-sm">Resumo profissional</strong>
            <span>Pacientes: <b>{portfolio.totalPatients}</b></span>
            <span>Devido: <b className="text-cyan-200">{financial?.total_due_brl || "R$ 0,00"}</b></span>
            <span>Recebido: <b className="text-emerald-200">{financial?.total_received_brl || "R$ 0,00"}</b></span>
            <span>Pendente: <b className="text-amber-100">{financial?.total_pending_brl || "R$ 0,00"}</b></span>
            <span>Carga média: <b>{Math.round(portfolio.meanClinicalLoad)}/100</b></span>
            <span>Continuidade: <b>{Math.round(portfolio.meanContinuity)}/100</b></span>
            <span>Para revisão: <b>{portfolio.reviewCount}</b></span>
          </div>
        </section>

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black">Pacientes e indicadores médios</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-max table-auto text-left text-[10px]">
                <thead className="uppercase text-slate-500">
                  <tr>{["Paciente", "Sessões", "IPM", "IDM", "P/min", "MFCC7", "MFCC9", "Jitter", "Shimmer", "Prioridade"].map((label) => <th key={label} className="px-2 py-2">{label}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {groups.map((group) => {
                    const signal = patientAdvancedSignal(group);
                    return (
                      <tr key={group.key} onClick={() => setSelectedKey(group.key)} className={`cursor-pointer hover:bg-slate-800 ${selected?.key === group.key ? "bg-cyan-950/40" : ""}`}>
                        <td className="px-2 py-2 font-black text-slate-100">{group.patient.name || "Paciente sem nome"}</td>
                        <td className="px-2 py-2">{group.totalSessions}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.ipmAvg), 1)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.idmAvg), 2)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.wordsPerMinute), 1)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.mfcc7), 3)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.mfcc9), 3)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.jitter), 3)}</td>
                        <td className="px-2 py-2">{fmt(mean(group.reports, (r) => r.sessionAverage.shimmer), 3)}</td>
                        <td className="px-2 py-2 font-bold text-cyan-200">{signal.priority}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="sticky top-4 rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-sm font-black">FROID Explica</h2>
              <button onClick={() => nav("/settings")} className="rounded border border-cyan-800 bg-cyan-950 px-3 py-1.5 text-[11px] font-bold text-cyan-100">Meus prompts</button>
            </div>
            {selected ? (
              <AIInsights
                zones={selected.latestReport.sessionAverage.zones || []}
                ipmScore={selected.latestReport.sessionAverage.ipmAvg}
                coherenceStatus={selected.latestReport.sessionAverage.coherenceStatus}
                baselineEstablished
                sessionId={selected.latestReport.sessionId}
                extraContext={{ patient: selected.patient, reports: selected.reports.slice(0, 20) }}
                controlsSticky
                messagesClassName="min-h-72 max-h-[520px]"
              />
            ) : <p className="text-xs text-slate-400">Nenhum paciente com relatório disponível.</p>}
          </section>
        </div>
      </main>
    </div>
  );
};
