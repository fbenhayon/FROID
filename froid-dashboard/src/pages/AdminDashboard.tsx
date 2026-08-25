import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { normalizeSearchText } from "../lib/patient-dashboard";
import {
  clearProductChoice,
  defaultAuthenticatedPath,
  readProductChoice,
} from "../lib/product-choice";

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

export const AdminDashboard: React.FC<Props> = ({ user }) => {
  // Para onde o "Dashboard" levaria de fato, pela mesma regra do roteamento.
  // Se for de volta para ca, o botao nao existe.
  const destinoDoDashboard = defaultAuthenticatedPath(user, readProductChoice());
  // Sem esta saida o administrador sem cadastro clinico concluido ficava sem
  // nenhum caminho para fora desta tela.
  const sair = () => {
    const token = localStorage.getItem("froid_token") || "";
    if (token && token !== "dev-local") {
      void fetch(apiUrl("/api/auth/logout"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
    }
    localStorage.removeItem("froid_token");
    localStorage.removeItem("froid_user");
    clearProductChoice();
    window.location.hash = "#/";
    window.location.reload();
  };
  const nav = useNavigate();
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [patientSearch, setPatientSearch] = useState("");

  const isFabio = Boolean(user?.access_status?.admin);

  useEffect(() => {
    const loadAdmin = async () => {
      setLoading(true);
      setMessage("");
      try {
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(apiUrl("/api/admin/overview"), {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const payload = response.ok ? await response.json() : null;
        if (!response.ok) {
          throw new Error(payload?.detail || "Acesso administrativo indisponível.");
        }
        setData(payload);
      } catch (error: any) {
        setMessage(error?.message || "Falha ao carregar painel administrativo.");
      } finally {
        setLoading(false);
      }
    };
    void loadAdmin();
  }, []);

  if (!isFabio) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-lg border border-red-900 bg-red-950/40 p-5">
          <p className="text-sm font-black uppercase tracking-[0.24em] text-red-200">
            Acesso restrito
          </p>
          <h1 className="mt-2 text-xl font-black">Controle administrativo FROID</h1>
          <p className="mt-2 text-sm text-red-100">
            Este painel e exclusivo do administrador do sistema.
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

  const summary = data?.summary || {};
  const professionals = Array.isArray(data?.professionals) ? data.professionals : [];
  const patients = Array.isArray(data?.patients) ? data.patients : [];
  const normalizedPatientSearch = normalizeSearchText(patientSearch);
  const patientSearchTokens = normalizedPatientSearch.split(/\s+/).filter(Boolean);
  const visiblePatients = patientSearchTokens.length
    ? patients.filter((patient: any) => {
        const haystack = normalizeSearchText(
          [patient.name, patient.email, patient.phone, patient.id]
            .filter(Boolean)
            .join(" "),
        );
        // Cada palavra digitada precisa aparecer em algum lugar (não
        // necessariamente contígua), para achar "Ana Souza" mesmo quando o
        // nome completo é "Ana Cecília Souza".
        return patientSearchTokens.every((token) => haystack.includes(token));
      })
    : patients;

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <main className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-300">
              Administracao FROID
            </p>
            <h1 className="mt-1 text-2xl font-black">Controle geral do sistema</h1>
            <p className="mt-1 text-xs text-slate-400">
              Profissionais, pacientes, sessões, convites e informativos financeiros totais.
            </p>
          </div>
          <div className="w-full max-w-xs shrink-0 sm:w-64">
            <input
              type="search"
              value={patientSearch}
              onChange={(event) => setPatientSearch(event.target.value)}
              placeholder="Buscar paciente..."
              aria-label="Buscar paciente"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:border-cyan-600 focus:outline-none"
            />
          </div>
          {/* O botao so aparece quando LEVA a algum lugar.
              /dashboard esta atras do onboarding clinico, e o administrador da
              plataforma que nunca comprou plano de sessoes para si mesmo e
              devolvido de la para ca — o botao virava um beco: clicava, a URL
              mudava, e a tela era a mesma. Perguntar antes de oferecer e mais
              honesto que oferecer e devolver. */}
          {destinoDoDashboard !== "/admin" && (
            <button
              onClick={() => nav(destinoDoDashboard)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
            >
              Dashboard
            </button>
          )}
          <button
            onClick={sair}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Sair
          </button>
        </header>

        {message && (
          <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-xs font-bold text-amber-100">
            {message}
          </p>
        )}

        {Number(summary.pending_professional_approvals) > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-500 bg-amber-950/60 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-lg">
                ⚠️
              </span>
              <div>
                <p className="text-sm font-black text-amber-100">
                  {summary.pending_professional_approvals}{" "}
                  {Number(summary.pending_professional_approvals) === 1
                    ? "novo profissional aguardando aprovação"
                    : "novos profissionais aguardando aprovação"}
                </p>
                <p className="text-[11px] text-amber-200/80">
                  Solicitações de acesso pendentes de análise. Clique para revisar
                  o cadastro e aprovar ou suspender.
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                const first = professionals.find(
                  (row: any) => row.manual_approval_status === "pending",
                );
                if (first)
                  nav(`/admin/professional/${encodeURIComponent(first.email)}`);
              }}
              className="rounded-lg bg-amber-500 px-4 py-2 text-xs font-black text-amber-950 hover:bg-amber-400"
            >
              Revisar solicitações
            </button>
          </div>
        )}

        <section className="grid gap-3 md:grid-cols-5">
          {[
            ["Profissionais", summary.professionals],
            ["Pacientes", summary.patients],
            ["Relatórios", summary.session_reports],
            ["Convites", summary.invites],
            ["Aprovações pendentes", summary.pending_professional_approvals],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-2 text-2xl font-black text-cyan-200">
                {loading ? "--" : value ?? 0}
              </p>
            </div>
          ))}
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          {[
            ["Total devido", summary.total_due_brl, "text-cyan-200"],
            ["Total recebido", summary.total_received_brl, "text-emerald-200"],
            ["Total pendente", summary.total_pending_brl, "text-amber-100"],
          ].map(([label, value, color]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className={`mt-2 text-xl font-black ${color}`}>{value || "R$ 0,00"}</p>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-slate-100">Profissionais</h2>
            <span className="text-[10px] text-slate-500">
              {professionals.length} no total · clique para abrir o perfil
            </span>
          </div>
          <div className="mt-3 max-h-[420px] overflow-auto rounded border border-slate-800">
            <table className="min-w-max table-auto text-left text-[10px] leading-tight">
              <thead className="sticky top-0 z-10 bg-slate-900 text-[9px] uppercase text-slate-500">
                <tr>
                  {[
                    "Profissional",
                    "Tipo",
                    "Plano",
                    "Pagamento",
                    "Acesso",
                    "Sessões",
                    "Saldo",
                    "Relatórios",
                    "Pacientes",
                    "Recebido",
                    "Pendente",
                  ].map((head) => (
                    <th key={head} className="whitespace-nowrap border-l border-slate-700 px-2 py-1 first:border-l-0">
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {professionals.map((row: any) => (
                  <tr
                    key={row.email}
                    onClick={() => nav(`/admin/professional/${encodeURIComponent(row.email)}`)}
                    className="cursor-pointer align-top hover:bg-cyan-950/20"
                    title="Abrir controle administrativo deste profissional"
                  >
                    <td className="whitespace-nowrap px-2 py-1 first:pl-0">
                      <p className="font-black text-slate-100">{row.name || row.email}</p>
                      <p className="text-[9px] text-slate-500">{row.email}</p>
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">{row.account_type || "--"}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">{row.selected_plan || "--"}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">{row.payment_status || "--"}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                      <span className={`rounded-full px-2 py-1 font-black uppercase ${
                        row.manual_approval_status === "approved"
                          ? "bg-emerald-950 text-emerald-200"
                          : row.manual_approval_status === "suspended"
                            ? "bg-red-950 text-red-200"
                            : "bg-amber-950 text-amber-100"
                      }`}>
                        {row.manual_approval_status === "approved"
                          ? "Aprovado"
                          : row.manual_approval_status === "suspended"
                            ? "Suspenso"
                            : "Aguardando"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-cyan-200">{row.used_sessions}/{row.total_sessions}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-black text-emerald-200">{row.remaining_sessions}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">{row.reports_count}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">{row.patients_count}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-emerald-200">{row.received_brl}</td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-amber-100">{row.pending_brl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-slate-100">Pacientes cadastrados</h2>
            <span className="text-[10px] text-slate-500">
              {normalizedPatientSearch
                ? `${visiblePatients.length} de ${patients.length} · clique para abrir o perfil`
                : `${patients.length} no total · clique para abrir o perfil`}
            </span>
          </div>
          <div className="mt-3 max-h-[420px] overflow-y-auto rounded border border-slate-800 p-1">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {visiblePatients.map((patient: any) => (
                <button
                  key={patient.id}
                  type="button"
                  onClick={() => nav(`/admin/patient/${encodeURIComponent(patient.id)}`)}
                  title="Abrir perfil deste paciente"
                  className="rounded border border-slate-800 bg-slate-950 p-3 text-left text-xs transition-colors hover:border-cyan-800 hover:bg-cyan-950/20"
                >
                  <p className="font-black text-slate-100">{patient.name}</p>
                  <p className="mt-1 text-slate-500">{patient.email || patient.phone || patient.id}</p>
                  <p className="mt-2 font-bold text-cyan-200">
                    {patient.sessions_count} sessões registradas
                  </p>
                </button>
              ))}
              {visiblePatients.length === 0 && (
                <p className="col-span-full py-6 text-center text-xs text-slate-500">
                  {patients.length === 0
                    ? "Nenhum paciente cadastrado ainda."
                    : "Nenhum paciente encontrado para esta busca."}
                </p>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};
