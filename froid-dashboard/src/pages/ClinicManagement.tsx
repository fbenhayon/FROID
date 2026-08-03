import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

type Props = { user?: FroidUser | null };

type ProfessionalUsage = {
  membership_id: string;
  email: string;
  roles: string[];
  sessions_used: number;
  patients: number;
  quota_sessions: number | null;
  quota_consumed: number | null;
  quota_remaining: number | null;
};

type UsageReport = {
  organization_id: string;
  pool_balance: number;
  pool_authority: string;
  report_visibility: "restricted" | "clinic_wide";
  sessions_used_total: number;
  professionals: ProfessionalUsage[];
};

const MANAGER_ROLES = new Set(["owner", "administrator"]);

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("froid_token") || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const ClinicManagement: React.FC<Props> = ({ user }) => {
  const nav = useNavigate();
  const [report, setReport] = useState<UsageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [unavailable, setUnavailable] = useState("");
  const [savingId, setSavingId] = useState("");
  const [quotaDrafts, setQuotaDrafts] = useState<Record<string, string>>({});
  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePhone, setInvitePhone] = useState("");
  const [inviteRole, setInviteRole] = useState("professional");
  const [inviting, setInviting] = useState(false);
  // O servidor devolve o token uma unica vez; guardamos em memoria apenas para
  // o gestor copiar e enviar por canal seguro. Nunca persistimos.
  const [invitation, setInvitation] = useState<{
    email: string;
    phone: string;
    token: string;
    hours: number;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const activeOrganization = useMemo(() => {
    const organizations = user?.organizations || [];
    return (
      organizations.find(
        (organization) => organization.organization_id === user?.active_organization_id,
      ) || organizations[0]
    );
  }, [user]);

  const organizationId = activeOrganization?.organization_id || "";
  const roles = useMemo(
    () => (activeOrganization?.roles || []).map((role) => String(role).toLowerCase()),
    [activeOrganization],
  );
  const isManager = roles.some((role) => MANAGER_ROLES.has(role));

  // Mensagem pronta para o WhatsApp. O código viaja no corpo da mensagem
  // porque é assim que o profissional o recebe; por isso o aviso de canal
  // seguro na tela continua valendo.
  const whatsappUrl = useMemo(() => {
    if (!invitation) return "";
    const clinicName = activeOrganization?.organization_name || "nossa clínica";
    const message =
      `Olá! Você foi convidado(a) para integrar a equipe de ${clinicName} no FROID.\n\n` +
      `1) Acesse ${window.location.origin}/app/#/login e entre (ou crie sua conta) com o e-mail ${invitation.email}.\n` +
      `2) Informe este código de convite:\n\n${invitation.token}\n\n` +
      `O código vale por ${invitation.hours} horas e é de uso único. Não o repasse a terceiros.`;
    const digits = invitation.phone.replace(/\D/g, "");
    return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
  }, [invitation, activeOrganization]);

  const loadReport = useCallback(async () => {
    if (!organizationId) {
      setLoading(false);
      setUnavailable("Nenhuma organização ativa nesta conta.");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${encodeURIComponent(organizationId)}/usage`),
        { headers: authHeaders() },
      );
      const payload = await response.json().catch(() => null);
      if (response.status === 409) {
        // Multi-organização ainda desligado no servidor: estado esperado
        // enquanto a persistência dual não é ativada, não um erro do usuário.
        setUnavailable(
          "A gestão multiprofissional ainda não está ativada neste servidor. Fale com a equipe FROID para habilitá-la para a sua clínica.",
        );
        setReport(null);
        return;
      }
      if (response.status === 403) {
        setUnavailable("Seu perfil não tem permissão para ver o relatório da clínica.");
        setReport(null);
        return;
      }
      if (!response.ok) {
        throw new Error(payload?.detail || "Não foi possível carregar o relatório.");
      }
      setUnavailable("");
      setReport(payload as UsageReport);
    } catch (error: any) {
      setMessage(error?.message || "Falha ao carregar o relatório da clínica.");
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const saveQuota = async (membershipId: string, raw: string) => {
    const trimmed = raw.trim();
    const quota = trimmed === "" ? null : Number(trimmed);
    if (quota !== null && (!Number.isFinite(quota) || quota < 0)) {
      setMessage("Cota inválida: use um número inteiro maior ou igual a zero, ou deixe vazio para liberar.");
      return;
    }
    setSavingId(membershipId);
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(membershipId)}/quota`,
        ),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            quota_sessions: quota === null ? null : Math.floor(quota),
          }),
        },
      );
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || "Não foi possível salvar a cota.");
      setMessage(
        quota === null
          ? "Cota removida: o profissional voltou a usar o pool livremente."
          : `Cota definida em ${Math.floor(quota)} sessões.`,
      );
      await loadReport();
    } catch (error: any) {
      setMessage(error?.message || "Falha ao salvar a cota.");
    } finally {
      setSavingId("");
    }
  };

  const sendInvite = async () => {
    const email = inviteEmail.trim().toLowerCase();
    if (!email || !email.includes("@")) {
      setMessage("Informe um e-mail válido para convidar o profissional.");
      return;
    }
    setInviting(true);
    setMessage("");
    setInvitation(null);
    setCopied(false);
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${encodeURIComponent(organizationId)}/members/invitations`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ email, roles: [inviteRole], expires_hours: 72 }),
        },
      );
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "Não foi possível gerar o convite.");
      }
      setInvitation({
        email,
        phone: invitePhone.trim(),
        token: String(payload?.invitation_token || ""),
        hours: Number(payload?.expires_in_hours || 72),
      });
      setInviteEmail("");
      setInvitePhone("");
      await loadReport();
    } catch (error: any) {
      setMessage(error?.message || "Falha ao convidar o profissional.");
    } finally {
      setInviting(false);
    }
  };

  const changeVisibility = async (visibility: "restricted" | "clinic_wide") => {
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${encodeURIComponent(organizationId)}/report-visibility`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ report_visibility: visibility }),
        },
      );
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "Não foi possível alterar a visibilidade.");
      }
      setMessage(
        visibility === "clinic_wide"
          ? "Visibilidade ampliada: todos os profissionais da clínica passam a ver os relatórios da clínica."
          : "Visibilidade restrita: cada profissional volta a ver apenas os pacientes atribuídos a ele.",
      );
      await loadReport();
    } catch (error: any) {
      setMessage(error?.message || "Falha ao alterar a visibilidade.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <main className="mx-auto max-w-6xl space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-300">
              Gestão da clínica
            </p>
            <h1 className="mt-1 text-2xl font-black">
              {activeOrganization?.organization_name || "Minha clínica"}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              Saldo compartilhado, uso por profissional, cotas individuais e
              visibilidade dos relatórios.
            </p>
          </div>
          <button
            onClick={() => nav("/dashboard")}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Voltar ao dashboard
          </button>
        </header>

        {unavailable && (
          <p className="rounded-lg border border-amber-700 bg-amber-950/40 px-4 py-3 text-xs font-semibold text-amber-100">
            {unavailable}
          </p>
        )}

        {message && (
          <p className="rounded-lg border border-cyan-800 bg-cyan-950/50 px-4 py-3 text-xs font-semibold text-cyan-100">
            {message}
          </p>
        )}

        {loading && (
          <p className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-6 text-center text-xs text-slate-400">
            Carregando relatório da clínica...
          </p>
        )}

        {report && (
          <>
            <section className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                  Sessões disponíveis para a clínica
                </p>
                <p className="mt-2 text-3xl font-black text-emerald-200">
                  {report.pool_balance}
                </p>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                  Sessões já utilizadas
                </p>
                <p className="mt-2 text-3xl font-black text-cyan-200">
                  {report.sessions_used_total}
                </p>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                  Profissionais na clínica
                </p>
                <p className="mt-2 text-3xl font-black text-slate-100">
                  {report.professionals.length}
                </p>
              </div>
            </section>

            {isManager && (
              <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <h2 className="text-sm font-black text-slate-100">
                  Convidar profissional para a clínica
                </h2>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                  O profissional precisa ter (ou criar) uma conta FROID com o
                  mesmo e-mail. Ao aceitar o convite, ele passa a consumir do
                  saldo compartilhado desta clínica.
                </p>
                <div className="mt-3 flex flex-wrap items-end gap-2">
                  <label className="flex-1 min-w-[220px] text-[10px] font-bold uppercase tracking-wide text-slate-500">
                    E-mail do profissional
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(event) => setInviteEmail(event.target.value)}
                      placeholder="profissional@clinica.com.br"
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-normal normal-case tracking-normal text-slate-100 placeholder:text-slate-600"
                    />
                  </label>
                  <label className="min-w-[170px] text-[10px] font-bold uppercase tracking-wide text-slate-500">
                    WhatsApp (opcional)
                    <input
                      type="tel"
                      value={invitePhone}
                      onChange={(event) => setInvitePhone(event.target.value)}
                      placeholder="5511988887777"
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-normal normal-case tracking-normal text-slate-100 placeholder:text-slate-600"
                    />
                  </label>
                  <label className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                    Papel
                    <select
                      value={inviteRole}
                      onChange={(event) => setInviteRole(event.target.value)}
                      className="mt-1 block rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-normal normal-case tracking-normal text-slate-100"
                    >
                      <option value="professional">Profissional</option>
                      <option value="supervisor">Supervisor</option>
                      <option value="administrator">Administrador</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    disabled={inviting}
                    onClick={() => void sendInvite()}
                    className="rounded-lg bg-cyan-700 px-4 py-2 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
                  >
                    {inviting ? "Gerando..." : "Gerar convite"}
                  </button>
                </div>

                {invitation && (
                  <div className="mt-3 rounded-lg border border-amber-700 bg-amber-950/40 p-3">
                    <p className="text-[11px] font-black text-amber-100">
                      Convite gerado para {invitation.email} · válido por{" "}
                      {invitation.hours}h
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed text-amber-200/90">
                      Este código aparece <strong>uma única vez</strong> e não
                      poderá ser recuperado. Envie-o ao profissional por um canal
                      seguro — quem tiver o código entra na sua clínica.
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <code className="min-w-0 flex-1 break-all rounded border border-amber-800 bg-slate-950 px-2 py-1.5 font-mono text-[10px] text-amber-100">
                        {invitation.token}
                      </code>
                      <button
                        type="button"
                        onClick={() => {
                          void navigator.clipboard
                            ?.writeText(invitation.token)
                            .then(() => setCopied(true))
                            .catch(() => setCopied(false));
                        }}
                        className="shrink-0 rounded border border-amber-600 bg-amber-900/60 px-3 py-1.5 text-[10px] font-black text-amber-100 hover:bg-amber-900"
                      >
                        {copied ? "Copiado" : "Copiar código"}
                      </button>
                      <a
                        href={whatsappUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 rounded border border-emerald-600 bg-emerald-900/60 px-3 py-1.5 text-[10px] font-black text-emerald-100 hover:bg-emerald-900"
                      >
                        Enviar por WhatsApp
                      </a>
                      <button
                        type="button"
                        onClick={() => setInvitation(null)}
                        className="shrink-0 rounded border border-slate-700 px-3 py-1.5 text-[10px] font-bold text-slate-300 hover:bg-slate-800"
                      >
                        Já enviei
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}

            <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <h2 className="text-sm font-black text-slate-100">
                Visibilidade dos relatórios
              </h2>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                Define quem, dentro da clínica, enxerga os relatórios dos
                pacientes. Amplia o acesso a dado sensível de saúde — a
                alteração fica registrada em auditoria.
              </p>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {(
                  [
                    {
                      value: "restricted" as const,
                      title: "Restrita (padrão)",
                      detail:
                        "Supervisor e gestor veem a clínica inteira; cada profissional vê apenas os pacientes atribuídos a ele.",
                    },
                    {
                      value: "clinic_wide" as const,
                      title: "Compartilhada na clínica",
                      detail:
                        "Todos os profissionais da clínica veem os relatórios da clínica, para análise conjunta de conduta.",
                    },
                  ]
                ).map((option) => {
                  const active = report.report_visibility === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      disabled={!isManager || active}
                      onClick={() => void changeVisibility(option.value)}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        active
                          ? "border-cyan-600 bg-cyan-950/60"
                          : "border-slate-700 bg-slate-950 hover:border-cyan-800"
                      } ${!isManager ? "cursor-not-allowed opacity-60" : ""}`}
                    >
                      <p className="text-xs font-black text-slate-100">
                        {option.title}
                        {active && (
                          <span className="ml-2 rounded bg-cyan-700 px-1.5 py-0.5 text-[9px] font-black text-white">
                            EM VIGOR
                          </span>
                        )}
                      </p>
                      <p className="mt-1 text-[10px] leading-relaxed text-slate-400">
                        {option.detail}
                      </p>
                    </button>
                  );
                })}
              </div>
              {!isManager && (
                <p className="mt-2 text-[10px] text-slate-500">
                  Somente o gestor da clínica pode alterar esta configuração.
                </p>
              )}
            </section>

            <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-black text-slate-100">
                  Profissionais, uso e cotas
                </h2>
                <span className="text-[10px] text-slate-500">
                  Cota vazia = usa o pool livremente
                </span>
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-max table-auto text-left text-[11px]">
                  <thead className="text-[9px] uppercase tracking-wide text-slate-500">
                    <tr>
                      {[
                        "Profissional",
                        "Papéis",
                        "Sessões usadas",
                        "Pacientes",
                        "Cota",
                        "Restante da cota",
                        "",
                      ].map((head) => (
                        <th key={head} className="whitespace-nowrap px-2 py-2">
                          {head}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {report.professionals.map((professional) => {
                      const draft =
                        quotaDrafts[professional.membership_id] ??
                        (professional.quota_sessions === null
                          ? ""
                          : String(professional.quota_sessions));
                      return (
                        <tr key={professional.membership_id} className="align-middle">
                          <td className="whitespace-nowrap px-2 py-2 font-bold text-slate-100">
                            {professional.email}
                          </td>
                          <td className="whitespace-nowrap px-2 py-2 text-slate-400">
                            {professional.roles.join(", ") || "--"}
                          </td>
                          <td className="px-2 py-2 font-mono text-cyan-200">
                            {professional.sessions_used}
                          </td>
                          <td className="px-2 py-2 font-mono text-slate-300">
                            {professional.patients}
                          </td>
                          <td className="px-2 py-2">
                            <input
                              type="number"
                              min={0}
                              value={draft}
                              disabled={!isManager}
                              placeholder="livre"
                              onChange={(event) =>
                                setQuotaDrafts((current) => ({
                                  ...current,
                                  [professional.membership_id]: event.target.value,
                                }))
                              }
                              className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[11px] text-slate-100 placeholder:text-slate-600 disabled:opacity-50"
                            />
                          </td>
                          <td className="px-2 py-2 font-mono text-slate-300">
                            {professional.quota_remaining === null
                              ? "—"
                              : professional.quota_remaining}
                          </td>
                          <td className="px-2 py-2">
                            {isManager && (
                              <button
                                type="button"
                                disabled={savingId === professional.membership_id}
                                onClick={() =>
                                  void saveQuota(professional.membership_id, draft)
                                }
                                className="rounded border border-cyan-800 bg-cyan-950 px-2 py-1 text-[10px] font-black text-cyan-100 hover:bg-cyan-900 disabled:opacity-40"
                              >
                                {savingId === professional.membership_id
                                  ? "Salvando..."
                                  : "Salvar"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {report.professionals.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-2 py-6 text-center text-slate-500">
                          Nenhum profissional ativo nesta clínica.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
};
