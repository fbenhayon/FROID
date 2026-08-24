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

function fmtNum(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "--";
}

export const AdminPatientDetail: React.FC<Props> = ({ user }) => {
  const nav = useNavigate();
  const params = useParams();
  const patientId = decodeURIComponent(params.patientId || "");
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const isFabio = Boolean(user?.access_status?.admin);

  useEffect(() => {
    const loadDetail = async () => {
      if (!patientId) return;
      setLoading(true);
      setMessage("");
      try {
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(
          apiUrl(`/api/admin/patients/${encodeURIComponent(patientId)}`),
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        const payload = response.ok ? await response.json() : null;
        if (!response.ok)
          throw new Error(payload?.detail || "Não foi possível carregar o paciente.");
        setData(payload);
      } catch (error: any) {
        setMessage(error?.message || "Falha ao carregar paciente.");
      } finally {
        setLoading(false);
      }
    };
    void loadDetail();
  }, [patientId]);

  if (!isFabio) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-lg border border-red-900 bg-red-950/40 p-5">
          <p className="text-sm font-black uppercase tracking-[0.24em] text-red-200">
            Acesso restrito
          </p>
          <h1 className="mt-2 text-xl font-black">Perfil de paciente</h1>
          <p className="mt-2 text-sm text-red-100">
            Este painel é exclusivo do administrador do sistema.
          </p>
          <button
            onClick={() => nav("/admin")}
            className="mt-4 rounded-lg bg-slate-950 px-4 py-2 text-xs font-bold text-white"
          >
            Voltar
          </button>
        </div>
      </div>
    );
  }

  const patient = data?.patient || {};
  const summary = data?.summary || {};
  const professionals = Array.isArray(data?.professionals) ? data.professionals : [];
  const reports = Array.isArray(data?.reports) ? data.reports : [];

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <main className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-300">
              Perfil do paciente
            </p>
            <h1 className="mt-1 text-2xl font-black">
              {loading ? "Carregando..." : patient.name || "Paciente"}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              {patient.email || patient.phone || patient.id}
            </p>
          </div>
          <button
            onClick={() => nav("/admin")}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Voltar ao admin
          </button>
        </header>

        {message && (
          <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-xs font-bold text-amber-100">
            {message}
          </p>
        )}

        <section className="grid gap-3 md:grid-cols-4">
          {[
            ["Relatórios", summary.reports],
            ["Profissionais", summary.professionals],
            ["Cadastrado em", fmtDate(patient.created_at)],
            ["Atualizado em", fmtDate(patient.updated_at)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-2 text-lg font-black text-cyan-200">
                {loading ? "--" : (value as any) ?? 0}
              </p>
            </div>
          ))}
        </section>

        {professionals.length > 0 && (
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black text-slate-100">
              Profissionais que atenderam
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {professionals.map((pro: any) => (
                <button
                  key={pro.email}
                  onClick={() =>
                    nav(`/admin/professional/${encodeURIComponent(pro.email)}`)
                  }
                  className="rounded-full border border-cyan-900 bg-cyan-950/40 px-3 py-1 text-[11px] font-bold text-cyan-100 hover:bg-cyan-900/50"
                  title="Abrir perfil administrativo do profissional"
                >
                  {pro.name || pro.email}
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-slate-100">
              Relatórios de sessão
            </h2>
            <span className="text-[10px] text-slate-500">
              {reports.length} · clique para abrir o relatório
            </span>
          </div>
          <div className="mt-3 max-h-[520px] space-y-2 overflow-y-auto pr-1">
            {reports.map((row: any, index: number) => (
              <button
                key={`${row.session_id}-${index}`}
                onClick={() =>
                  row.session_id &&
                  nav(`/session/${encodeURIComponent(row.session_id)}/report`)
                }
                className="block w-full rounded border border-slate-800 bg-slate-950 p-3 text-left text-xs transition-colors hover:border-cyan-800 hover:bg-cyan-950/20"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-black text-slate-100">
                    {fmtDate(row.created_at)}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {row.professional_name || row.professional_email}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-300">
                  <span>
                    <b className="text-slate-500">IPM:</b> {fmtNum(row.ipm)}
                  </span>
                  <span>
                    <b className="text-slate-500">IDM:</b> {fmtNum(row.idm, 2)}
                  </span>
                  <span>
                    <b className="text-slate-500">Zona:</b>{" "}
                    {row.dominant_zone ?? "--"}
                  </span>
                  <span>
                    <b className="text-slate-500">Coerência:</b>{" "}
                    {row.coherence || "--"}
                  </span>
                </div>
                {row.theme && (
                  <p className="mt-1 text-[11px] text-slate-400">{row.theme}</p>
                )}
              </button>
            ))}
            {reports.length === 0 && !loading && (
              <p className="py-6 text-center text-xs text-slate-500">
                Nenhum relatório de sessão para este paciente.
              </p>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};
