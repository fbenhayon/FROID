import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

interface Props {
  user?: FroidUser | null;
}

// Quem e administrador e decisao do servidor, nao do pacote do navegador.
//
// Esta lista estava fixa em TRES arquivos, com um unico endereco. O efeito
// pratico: o Fabio entrou com fbenhayon@froid.com.br e recebeu "acesso
// restrito" nas tres telas de admin, sem que nada no sistema explicasse por
// que — o backend ja le FROID_ADMIN_EMAILS e ja devolve access_status.admin,
// e o painel ignorava as duas coisas. Acrescentar um administrador exigiria
// build novo do painel em vez de uma variavel de ambiente.

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
  const [approvalLoading, setApprovalLoading] = useState(false);
  const isFabio = Boolean(user?.access_status?.admin);

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
        if (!response.ok) throw new Error(payload?.detail || "Não foi possível carregar o profissional.");
        setData(payload);
      } catch (error: any) {
        setMessage(error?.message || "Falha ao carregar profissional.");
      } finally {
        setLoading(false);
      }
    };
    void loadDetail();
  }, [professionalEmail]);

  const changeApproval = async (nextStatus: "approved" | "suspended") => {
    const verb = nextStatus === "approved" ? "aprovar" : "suspender";
    if (!window.confirm(`Confirma ${verb} o acesso de ${professionalEmail}?`)) return;
    setApprovalLoading(true);
    setMessage("");
    try {
      const token = localStorage.getItem("froid_token") || "";
      const response = await fetch(
        apiUrl(`/api/admin/professionals/${encodeURIComponent(professionalEmail)}/access-approval`),
        {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status: nextStatus }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail || "Não foi possível alterar a aprovação.");
      setData((current: any) => ({
        ...current,
        profile: { ...(current?.profile || {}), access_approval_status: nextStatus },
        access_status: payload.access_status,
      }));
      setMessage(nextStatus === "approved" ? "Acesso profissional aprovado." : "Acesso profissional suspenso.");
    } catch (error: any) {
      setMessage(error?.message || "Falha ao alterar a aprovação.");
    } finally {
      setApprovalLoading(false);
    }
  };

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

        <section className="overflow-x-auto pb-1">
          <div className="grid min-w-[980px] grid-cols-7 gap-2">
            {[
              ["Pacientes", summary.patients, "text-cyan-200"],
              ["Relatórios", summary.reports, "text-cyan-200"],
              ["Convites", summary.invites, "text-cyan-200"],
              ["Saldo", status.remaining_sessions, "text-cyan-200"],
              ["Devido", summary.total_due_brl, "text-cyan-200"],
              ["Recebido", summary.total_received_brl, "text-emerald-200"],
              ["Pendente", summary.total_pending_brl, "text-amber-100"],
            ].map(([label, value, color]) => (
              <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2.5">
                <p className="whitespace-nowrap text-[9px] font-black uppercase tracking-wide text-slate-500">
                  {label}
                </p>
                <p className={`mt-1 whitespace-nowrap text-lg font-black ${color}`}>
                  {loading ? "--" : value ?? (String(label) === "Devido" || String(label) === "Recebido" || String(label) === "Pendente" ? "R$ 0,00" : 0)}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-black text-slate-100">Cadastro, créditos e acesso</h2>
              <p className="mt-1 text-xs text-slate-400">
                Aprovação manual durante a fase controlada de testes.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-wide ${
                  status.manual_approval_status === "approved"
                    ? "border-emerald-700 bg-emerald-950 text-emerald-200"
                    : status.manual_approval_status === "suspended"
                      ? "border-red-700 bg-red-950 text-red-200"
                      : "border-amber-700 bg-amber-950 text-amber-100"
                }`}
              >
                {status.manual_approval_status === "approved"
                  ? "Aprovado"
                  : status.manual_approval_status === "suspended"
                    ? "Suspenso"
                    : "Aguardando aprovação"}
              </span>
              {/* Aprovar e suspender tinham exatamente a mesma cor. Um
                  botão ciano dizia "Aprovar acesso" e, um clique depois, o
                  mesmo botão ciano dizia "Suspender acesso" — a ação
                  destrutiva com a aparência da construtiva, no mesmo lugar
                  da tela. Quem clicasse duas vezes por dúvida derrubava o
                  acesso de um cliente sem perceber que tinha mudado de
                  verbo. */}
              <button
                type="button"
                disabled={approvalLoading}
                onClick={() => void changeApproval(
                  status.manual_approval_status === "approved" ? "suspended" : "approved",
                )}
                className={`rounded-lg border px-3 py-2 text-xs font-black disabled:cursor-wait disabled:opacity-50 ${
                  status.manual_approval_status === "approved"
                    ? "border-red-700 bg-red-950 text-red-100 hover:bg-red-900"
                    : "border-emerald-600 bg-emerald-700 text-white hover:bg-emerald-600"
                }`}
              >
                {approvalLoading
                  ? "Processando..."
                  : status.manual_approval_status === "approved"
                    ? "Suspender acesso"
                    : "Aprovar acesso"}
              </button>
            </div>
          </div>
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
                {status.used_sessions ?? 0}/{status.total_sessions ?? 0} sessões
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black text-slate-100">Relatórios recentes</h2>
            <div className="mt-3 max-h-[360px] space-y-2 overflow-y-auto pr-1">
              {reports.slice(0, 3).map((report: any) => (
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
            <div className="mt-3 max-h-[360px] space-y-2 overflow-y-auto pr-1">
              {receivables.slice(0, 3).map((item: any) => (
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
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  {patient.email && (
                    <a className="text-slate-400 hover:text-cyan-200 hover:underline" href={`mailto:${patient.email}`}>
                      {patient.email}
                    </a>
                  )}
                  {patient.phone && (
                    <a className="font-bold text-cyan-300 hover:text-cyan-100 hover:underline" href={`tel:${patient.phone}`}>
                      {patient.phone}
                    </a>
                  )}
                  {!patient.email && !patient.phone && (
                    <span className="text-slate-500">{patient.id || "--"}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};
