import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

interface Props {
  user?: FroidUser | null;
}

const adminEmails = new Set(["fbenhayon@gmail.com"]);

function fmtDate(value?: string) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString("pt-BR") : "--";
}

export const AdminProfessionalDetail: React.FC<Props> = ({ user }) => {
  const nav = useNavigate();
  const params = useParams();
  const professionalEmail = decodeURIComponent(params.professionalEmail || "");
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const isFabio = adminEmails.has(String(user?.email || "").toLowerCase());

  useEffect(() => {
    const loadDetail = async () => {
      if (!professionalEmail) return;
      setLoading(true);
      setMessage("");
      try {
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(
          apiUrl(`/api/admin/professionals/${encodeURIComponent(professionalEmail)}`),
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        const payload = response.ok ? await response.json() : null;
        if (!response.ok) throw new Error(payload?.detail || "Nao foi possivel carregar o profissional.");
        setData(payload);
      } catch (error: any) {
        setMessage(error?.message || "Falha ao carregar profissional.");
      } finally {
        setLoading(false);
      }
    };
    void loadDetail();
  }, [professionalEmail]);

  if (!isFabio) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-5">
          <p className="text-sm font-black uppercase tracking-[0.24em] text-red-200">
            Acesso restrito
          </p>
          <button
            onClick={() => nav("/dashboard")}
            className="mt-4 rounded-lg bg-slate-950 px-4 py-2 text-xs font-bold text-white"
          >
            Voltar
          </button>
        </div>
      </div>
    );
  }

  const profile = data?.profile || {};
  const status = data?.access_status || {};
  const summary = data?.summary || {};
  const reports = Array.isArray(data?.reports) ? data.reports : [];
  const receivables = Array.isArray(data?.receivables) ? data.receivables : [];
  const patients = Array.isArray(data?.patients) ? data.patients : [];

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <main className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-300">
              Profissional
            </p>
            <h1 className="mt-1 text-2xl font-black">
              {profile.owner_name || profile.organization_name || professionalEmail}
            </h1>
            <p className="mt-1 text-xs text-slate-400">{professionalEmail}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => nav("/admin")}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
            >
              Admin
            </button>
            <button
              onClick={() => nav("/dashboard")}
              className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
            >
              Dashboard
            </button>
          </div>
        </header>

        {message && (
          <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-xs font-bold text-amber-100">
            {message}
          </p>
        )}

        <section className="grid gap-3 md:grid-cols-4">
          {[
            ["Pacientes", summary.patients],
            ["Relatorios", summary.reports],
            ["Convites", summary.invites],
            ["Saldo", status.remaining_sessions],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">{label}</p>
              <p className="mt-2 text-2xl font-black text-cyan-200">{loading ? "--" : value ?? 0}</p>
            </div>
          ))}
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          {[
            ["Devido", summary.total_due_brl, "text-cyan-200"],
            ["Recebido", summary.total_received_brl, "text-emerald-200"],
            ["Pendente", summary.total_pending_brl, "text-amber-100"],
          ].map(([label, value, color]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">{label}</p>
              <p className={`mt-2 text-xl font-black ${color}`}>{value || "R$ 0,00"}</p>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="text-sm font-black text-slate-100">Cadastro e creditos</h2>
          <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
            <div className="rounded border border-slate-800 bg-slate-950 p-3">
              <p className="font-black uppercase text-slate-500">Tipo</p>
              <p className="mt-1 font-bold text-slate-200">{profile.account_type || "--"}</p>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950 p-3">
              <p className="font-black uppercase text-slate-500">Plano</p>
              <p className="mt-1 font-bold text-slate-200">{profile.selected_plan || "--"}</p>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950 p-3">
              <p className="font-black uppercase text-slate-500">Uso</p>
              <p className="mt-1 font-bold text-slate-200">
                {status.used_sessions ?? 0}/{status.total_sessions ?? 0} sessoes
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black text-slate-100">Relatorios recentes</h2>
            <div className="mt-3 space-y-2">
              {reports.slice(0, 20).map((report: any) => (
                <button
                  key={report.session_id}
                  type="button"
                  onClick={() => nav(`/session/${report.session_id}/report`)}
                  className="block w-full rounded border border-slate-800 bg-slate-950 p-3 text-left text-xs hover:border-cyan-800"
                >
                  <p className="font-black text-cyan-200">{fmtDate(report.created_at)}</p>
                  <p className="mt-1 font-bold text-slate-100">
                    {report.patient?.name || "Paciente sem nome"} | IPM {report.ipm ?? "--"} | IDM {report.idm ?? "--"} | Zona {report.dominant_zone ?? "--"}
                  </p>
                  <p className="mt-1 line-clamp-2 text-slate-400">{report.summary || report.theme || "Sem resumo."}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black text-slate-100">Recebimentos e convites</h2>
            <div className="mt-3 space-y-2">
              {receivables.slice(0, 30).map((item: any) => (
                <div key={`${item.invite_id}-${item.session_id}`} className="rounded border border-slate-800 bg-slate-950 p-3 text-xs">
                  <p className="font-black text-slate-100">{item.patient?.name || "Paciente sem nome"}</p>
                  <p className="mt-1 text-slate-500">{item.session_id || item.invite_id}</p>
                  <p className="mt-2 font-bold text-cyan-200">
                    Devido {item.due_brl} | Recebido {item.received_brl} | Status {item.payment_status || item.status || "--"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="text-sm font-black text-slate-100">Pacientes vinculados</h2>
          <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {patients.slice(0, 90).map((patient: any, index: number) => (
              <div key={`${patient.id || patient.email || patient.phone || patient.name}-${index}`} className="rounded border border-slate-800 bg-slate-950 p-3 text-xs">
                <p className="font-black text-slate-100">{patient.name || "Paciente sem nome"}</p>
                <p className="mt-1 text-slate-500">{patient.email || patient.phone || patient.id || "--"}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};
