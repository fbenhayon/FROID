import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { normalizeSearchText } from "../lib/patient-dashboard";
import { ControleDeAcesso } from "../components/admin/ControleDeAcesso";
import {
  clearProductChoice,
  defaultAuthenticatedPath,
  readProductChoice,
} from "../lib/product-choice";
import {
  irParaContexto,
  nomeDaOrganizacao,
  organizacaoClinica,
  organizacoesNr1,
} from "../lib/contexto-organizacao";

interface Props {
  user?: FroidUser | null;
}

/**
 * Por que o painel clinico nao esta alcancavel, e para onde ir resolver.
 *
 * O administrador da plataforma nao compra pacote de sessoes para si mesmo,
 * entao `onboarding_required` fica verdadeiro para sempre e
 * `defaultAuthenticatedPath` o devolve para /admin. O commit anterior tratou
 * isso escondendo o botao "Dashboard" quando ele nao levaria a lugar nenhum —
 * o que era honesto e produziu um beco PIOR: sobrava um botao so na tela, e
 * era o "Sair". Quem precisasse atender um paciente encerrava a sessao.
 *
 * Botao escondido nao informa. O certo e dizer o que falta e oferecer a porta
 * que resolve — que existe, e nunca esteve atras do onboarding.
 */
export function pendenciaDoAdministrador(
  user?: FroidUser | null,
): { motivo: string; destino: string; rotulo: string } | null {
  const acesso = user?.access_status;
  if (!acesso || !acesso.onboarding_required) return null;
  if (acesso.manual_approval_pending) {
    return {
      motivo: "Seu cadastro clínico está aguardando aprovação.",
      destino: "/admin",
      rotulo: "",
    };
  }
  if (!acesso.has_profile) {
    return {
      motivo: "Você ainda não tem cadastro clínico nesta conta.",
      destino: "/access/produto",
      rotulo: "Concluir meu cadastro",
    };
  }
  if (!acesso.selected_plan) {
    return {
      motivo:
        "Seu cadastro clínico não tem plano de sessões escolhido, e é o saldo " +
        "de sessões que libera o painel de atendimento.",
      destino: "/access/register",
      rotulo: "Escolher plano de sessões",
    };
  }
  if ((acesso.remaining_sessions ?? 0) <= 0) {
    return {
      motivo:
        "Seu cadastro clínico está sem saldo de sessões, e o painel de " +
        "atendimento depende dele.",
      destino: "/access/register",
      rotulo: "Repor saldo de sessões",
    };
  }
  return {
    motivo: "Seu cadastro clínico tem pendências.",
    destino: "/access/register",
    rotulo: "Revisar meu cadastro",
  };
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
  // Quando o destino volta para ca, o painel clinico esta atras de alguma
  // pendencia. Em vez de esconder o botao, dizemos qual e e para onde ir.
  const pendencia =
    destinoDoDashboard === "/admin" ? pendenciaDoAdministrador(user) : null;
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
    // #/login, e nao #/ — a raiz do painel renderizava uma COPIA congelada do
    // site institucional, 17 dias mais velha que o site de verdade. Sair pela
    // porta dos fundos e cair num site desatualizado e pior que nao ter porta.
    window.location.hash = "#/login";
    window.location.reload();
  };
  const nav = useNavigate();
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [patientSearch, setPatientSearch] = useState("");

  // As empresas contratantes do NR-1 desta conta. Vêm do /api/auth/me, que já
  // devolve organization_type por organização — não há chamada nova.
  const clientesNr1 = organizacoesNr1(user);
  const [erroDeContexto, setErroDeContexto] = useState("");
  const abrirNr1 = async (organizationId: string) => {
    setErroDeContexto("");
    const erro = await irParaContexto(organizationId, "/nr1");
    if (erro) setErroDeContexto(erro);
  };

  // O caminho de volta, simétrico ao de cima.
  //
  // Sem isto o laço ficava aberto: quem entrasse numa empresa NR-1 por esta
  // tela voltava para o painel clínico com a organização 'enterprise' ainda
  // ativa — e lá os pacientes não aparecem, porque a organização do empregador
  // não carrega as permissões clínicas identificadas.
  const organizacaoDoPsique = organizacaoClinica(user);
  const irParaODashboard = async () => {
    setErroDeContexto("");
    if (
      !organizacaoDoPsique ||
      organizacaoDoPsique.organization_id === user?.active_organization_id
    ) {
      nav(destinoDoDashboard);
      return;
    }
    const erro = await irParaContexto(
      organizacaoDoPsique.organization_id,
      destinoDoDashboard,
    );
    if (erro) setErroDeContexto(erro);
  };

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
          {destinoDoDashboard !== "/admin" ? (
            <button
              onClick={() => void irParaODashboard()}
              className="rounded-lg border border-cyan-700 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
            >
              Dashboard
            </button>
          ) : (
            pendencia?.rotulo && (
              <button
                onClick={() => nav(pendencia.destino)}
                title={pendencia.motivo}
                className="rounded-lg border border-cyan-700 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
              >
                {pendencia.rotulo}
              </button>
            )
          )}
          {/* A empresa NR-1 do administrador nao passa pelo onboarding
              clinico, entao esta porta continua aberta mesmo quando a outra
              nao esta. Num dia de atendimento ou de reuniao, e ela que evita
              que a unica saida da tela seja encerrar a sessao. */}
          {/* Leva a organização junto quando há uma.
              O botão apenas navegava, e o painel NR-1 lê a organização ATIVA
              da sessão: chegando lá com a organização clínica ativa, todo
              endpoint do módulo responde 409 ("disponível apenas para
              organizações do tipo enterprise") e a tela abre vazia. Funcionava
              por acaso — só enquanto a sessão já estivesse na empresa. */}
          <button
            onClick={() => {
              if (clientesNr1.length > 0) {
                void abrirNr1(clientesNr1[0].organization_id);
              } else {
                nav("/nr1");
              }
            }}
            title="Painel de conformidade NR-1"
            className="rounded-lg border border-amber-700 bg-amber-950 px-3 py-2 text-xs font-bold text-amber-100 hover:bg-amber-900"
          >
            NR-1
          </button>
          <button
            onClick={sair}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Sair
          </button>
        </header>

        {pendencia && (
          <p className="rounded-lg border border-cyan-800 bg-cyan-950/40 px-3 py-3 text-xs leading-5 text-cyan-100">
            <strong className="text-cyan-200">
              O painel de atendimento não está acessível nesta conta.
            </strong>{" "}
            {pendencia.motivo}{" "}
            {pendencia.rotulo
              ? "Use o botão acima para resolver — e note que administrar a plataforma e atender pacientes são coisas separadas: uma não depende da outra."
              : "Nada a fazer aqui: assim que a aprovação sair, o painel aparece."}
          </p>
        )}

        {message && (
          <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-xs font-bold text-amber-100">
            {message}
          </p>
        )}

        {/* Clientes NR-1: a porta de entrada de cada empresa contratante.
            O seletor de organização do painel clínico foi retirado — lá ele
            não abria nada do NR-1, só estreitava as permissões e fazia os
            pacientes sumirem da tela. A troca de contexto passa a acontecer
            aqui, onde ela tem um destino: o painel de conformidade.

            A lista é das empresas de que ESTA CONTA é membro, e não de todas
            as empresas da plataforma: /api/auth/active-organization responde
            403 sem vínculo, então listar mais seria oferecer link morto. Para
            entrar numa empresa nova, o caminho é conceder o vínculo no
            Controle de acesso, abaixo. */}
        <section className="rounded-lg border border-amber-900/60 bg-slate-900 p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-black text-amber-100">Clientes NR-1</h2>
            <p className="text-[11px] text-slate-500">
              Empresas contratantes vinculadas a esta conta. Abrir troca a
              organização ativa da sessão.
            </p>
          </div>

          {erroDeContexto && (
            <p className="mt-3 rounded border border-red-900 bg-red-950 px-3 py-2 text-xs font-bold text-red-200">
              {erroDeContexto}
            </p>
          )}

          {clientesNr1.length === 0 ? (
            <p className="mt-3 text-xs leading-5 text-slate-400">
              Nenhuma empresa NR-1 vinculada a esta conta. O painel de
              conformidade é escopado por organização do tipo{" "}
              <code className="text-slate-300">enterprise</code>, e o acesso vem
              do vínculo — não do papel de administrador. Use o Controle de
              acesso para conceder o vínculo a esta conta na empresa desejada.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {clientesNr1.map((cliente) => {
                const ativa =
                  cliente.organization_id === user?.active_organization_id;
                return (
                  <li
                    key={cliente.organization_id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded border border-slate-800 bg-slate-950 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-black text-slate-100">
                        {nomeDaOrganizacao(cliente)}
                        {ativa && (
                          <span className="ml-2 rounded bg-emerald-950 px-2 py-0.5 text-[10px] font-black uppercase tracking-wide text-emerald-300">
                            contexto ativo
                          </span>
                        )}
                      </p>
                      <p className="truncate text-[10px] text-slate-500">
                        {cliente.organization_id}
                        {cliente.roles?.length
                          ? ` · ${cliente.roles.join(", ")}`
                          : ""}
                      </p>
                    </div>
                    <button
                      onClick={() => void abrirNr1(cliente.organization_id)}
                      className="shrink-0 rounded border border-amber-700 bg-amber-950 px-3 py-2 text-xs font-black text-amber-100 hover:bg-amber-900"
                    >
                      Abrir painel NR-1
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

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

        <ControleDeAcesso />

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-slate-100">Pacientes cadastrados</h2>
            <span className="text-[10px] text-slate-500">
              {normalizedPatientSearch
                ? `${visiblePatients.length} de ${patients.length} · clique para abrir o perfil`
                : `${patients.length} no total · clique para abrir o perfil`}
            </span>
          </div>
          {/* Listagem, e nao grade de cartoes: com muitos pacientes a grade de
              tres colunas obriga a varrer em ziguezague. Em lista o olho desce
              reto, e o cabecalho fica fixo enquanto se rola. */}
          <div className="mt-3 max-h-[420px] overflow-y-auto rounded border border-slate-800">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 z-10 bg-slate-900">
                <tr className="text-[10px] uppercase tracking-wide text-slate-500">
                  <th className="border-b border-slate-800 px-3 py-2 text-left font-black">Paciente</th>
                  <th className="border-b border-slate-800 px-3 py-2 text-left font-black">Contato</th>
                  <th className="border-b border-slate-800 px-3 py-2 text-left font-black">Atendido por</th>
                  <th className="border-b border-slate-800 px-3 py-2 text-right font-black">Sessões</th>
                </tr>
              </thead>
              <tbody>
              {visiblePatients.map((patient: any) => (
                <tr
                  key={patient.id}
                  onClick={() => nav(`/admin/patient/${encodeURIComponent(patient.id)}`)}
                  title="Abrir perfil deste paciente"
                  className="cursor-pointer border-b border-slate-800/60 transition-colors hover:bg-cyan-950/20"
                >
                  <td className="px-3 py-2 font-black text-slate-100">{patient.name}</td>
                  <td className="px-3 py-2 text-slate-500">
                    {patient.email || patient.phone || patient.id}
                  </td>
                  {/* Um paciente pode ser atendido por mais de um profissional:
                      encaminhamento, segunda opinião, troca de terapeuta. */}
                  <td className="px-3 py-2 text-slate-300">
                    {(patient.professionals || []).length === 0 ? (
                      <span className="text-slate-600">—</span>
                    ) : (
                      (patient.professionals || [])
                        .map((p: any) => p.name || p.email)
                        .join(" · ")
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-bold tabular-nums text-cyan-200">
                    {patient.sessions_count}
                  </td>
                </tr>
              ))}
              {visiblePatients.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-xs text-slate-500">
                    {patients.length === 0
                      ? "Nenhum paciente cadastrado ainda."
                      : "Nenhum paciente encontrado para esta busca."}
                  </td>
                </tr>
              )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
};
