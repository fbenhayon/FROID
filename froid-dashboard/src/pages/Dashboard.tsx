import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../lib/api";

interface DashboardProps {
  user?: any;
}

type PaymentMode = "package" | "single";

interface InviteResult {
  token: string;
  session_id: string;
  invite_url: string;
  whatsapp_url: string;
  whatsapp_message: string;
  patient_known: boolean;
  payment: {
    mode: PaymentMode;
    package_sessions: number;
    session_value_cents: number;
    session_value_brl: string;
    package_total_cents: number;
    package_total_brl: string;
    pix_code: string;
    payment_status: string;
  };
}

function makeId() {
  return (
    "froid-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  );
}

const initialInviteForm = {
  patient_name: "",
  patient_email: "",
  patient_phone: "",
  payment_mode: "single" as PaymentMode,
  session_value: "",
  package_sessions: "4",
  pix_code: "",
};

export const Dashboard: React.FC<DashboardProps> = ({ user }) => {
  const nav = useNavigate();
  const [form, setForm] = useState(initialInviteForm);
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null);
  const professionalName = user?.name || user?.email || "Dr. Profissional";

  const currentOrigin = useMemo(
    () => (typeof window !== "undefined" ? window.location.origin : ""),
    [],
  );

  const updateForm = (key: keyof typeof initialInviteForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const createInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreatingInvite(true);
    setInviteError("");
    setInviteResult(null);

    try {
      const response = await fetch(apiUrl("/api/session-invites"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          session_id: makeId(),
          base_url: currentOrigin,
          package_sessions: Number(form.package_sessions || 0),
          session_value: form.session_value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(
            "Modulo de convites indisponivel no backend. Reinicie ou atualize o servidor FROID.",
          );
        }
        throw new Error(data?.detail || "Nao foi possivel criar o convite.");
      }
      setInviteResult(data);
    } catch (err) {
      setInviteError(
        err instanceof Error ? err.message : "Falha ao criar convite.",
      );
    } finally {
      setCreatingInvite(false);
    }
  };

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard?.writeText(text);
    } catch {
      window.prompt("Copie o conteudo abaixo:", text);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
            F
          </div>
          <h1 className="text-lg font-bold tracking-tight">
            FROID{" "}
            <span className="font-normal text-slate-400">
              | Dashboard Profissional
            </span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{professionalName}</span>
          <div className="h-8 w-8 rounded-full bg-slate-200" />
        </div>
      </header>

      <main className="mx-auto max-w-6xl p-6">
        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
          <button
            onClick={() => nav(`/session/${makeId()}`)}
            className="rounded-xl bg-blue-600 p-5 text-left text-white shadow-sm transition-colors hover:bg-blue-700"
          >
            <div className="mb-1 text-2xl">+</div>
            <h2 className="text-sm font-bold uppercase tracking-wide">
              Nova Sessao Direta
            </h2>
            <p className="mt-1 text-[11px] opacity-80">
              Iniciar sala clinica sem convite de paciente.
            </p>
          </button>

          <button
            onClick={() => nav("/history")}
            className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition-colors hover:bg-slate-50"
          >
            <div className="mb-1 text-2xl">H</div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">
              Historico
            </h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Sessoes arquivadas e prontuario criptografado.
            </p>
          </button>

          <button
            onClick={() => nav("/settings")}
            className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition-colors hover:bg-slate-50"
          >
            <div className="mb-1 text-2xl">C</div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">
              Configuracoes
            </h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Agenda, consentimentos, auditoria e credenciais.
            </p>
          </button>
        </div>

        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Convite de sessao ao paciente
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Gere o link publico, defina a forma de pagamento e copie a
                mensagem padrao para colar no WhatsApp do paciente.
              </p>
            </div>
            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-blue-700">
              Algoritmo inicial
            </span>
          </div>

          <form onSubmit={createInvite} className="grid gap-3 lg:grid-cols-4">
            <label className="text-xs font-semibold text-slate-600">
              Nome do paciente
              <input
                value={form.patient_name}
                onChange={(event) => updateForm("patient_name", event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                placeholder="Nome completo"
              />
            </label>
            <label className="text-xs font-semibold text-slate-600">
              WhatsApp
              <input
                value={form.patient_phone}
                onChange={(event) => updateForm("patient_phone", event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                placeholder="5511999999999"
              />
            </label>
            <label className="text-xs font-semibold text-slate-600">
              E-mail
              <input
                value={form.patient_email}
                onChange={(event) => updateForm("patient_email", event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                placeholder="paciente@email.com"
              />
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Forma de pagamento
              <select
                value={form.payment_mode}
                onChange={(event) =>
                  updateForm("payment_mode", event.target.value as PaymentMode)
                }
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
              >
                <option value="single">Sessao avulsa com PIX</option>
                <option value="package">Pacote de sessoes</option>
              </select>
            </label>

            <label className="text-xs font-semibold text-slate-600">
              Valor da sessao (R$)
              <input
                value={form.session_value}
                onChange={(event) => updateForm("session_value", event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                placeholder="Ex.: 300,00"
              />
            </label>

            {form.payment_mode === "package" ? (
              <label className="text-xs font-semibold text-slate-600">
                Numero de sessoes do pacote
                <input
                  type="number"
                  min={1}
                  value={form.package_sessions}
                  onChange={(event) =>
                    updateForm("package_sessions", event.target.value)
                  }
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                />
              </label>
            ) : (
              <label className="text-xs font-semibold text-slate-600 lg:col-span-2">
                Codigo PIX copia e cola
                <input
                  value={form.pix_code}
                  onChange={(event) => updateForm("pix_code", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                  placeholder="Cole aqui o codigo PIX que sera enviado junto ao convite."
                />
              </label>
            )}

            <div className="lg:self-end">
              <button
                type="submit"
                disabled={creatingInvite}
                className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {creatingInvite ? "Gerando convite..." : "Gerar convite"}
              </button>
              {inviteError && (
                <span className="mt-1 block text-xs font-semibold text-red-600">
                  {inviteError}
                </span>
              )}
            </div>
          </form>

          {inviteResult && (
            <div className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-bold text-emerald-900">
                    Convite criado
                  </p>
                  <p className="text-[11px] text-emerald-700">
                    Sessao: {inviteResult.session_id} - Paciente{" "}
                    {inviteResult.patient_known ? "ja cadastrado" : "novo cadastro"}
                  </p>
                  <p className="text-[11px] text-emerald-700">
                    Valor: {inviteResult.payment.session_value_brl}
                    {inviteResult.payment.mode === "package"
                      ? ` - Total pacote: ${inviteResult.payment.package_total_brl}`
                      : ""}
                  </p>
                </div>
                <button
                  onClick={() => nav(`/session/${inviteResult.session_id}`)}
                  className="rounded-md bg-white px-3 py-1.5 text-xs font-bold text-emerald-700 shadow-sm hover:bg-emerald-100"
                >
                  Abrir sala profissional
                </button>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                <button
                  onClick={() => copyText(inviteResult.whatsapp_message)}
                  className="rounded-md bg-slate-900 px-3 py-2 text-center text-xs font-bold text-white hover:bg-slate-800"
                >
                  Copiar mensagem padrao
                </button>
                <button
                  onClick={() => copyText(inviteResult.invite_url)}
                  className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-left text-xs font-semibold text-slate-700"
                >
                  Copiar link direto
                </button>
                {inviteResult.whatsapp_url && (
                  <a
                    href={inviteResult.whatsapp_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md bg-green-600 px-3 py-2 text-center text-xs font-bold text-white hover:bg-green-700"
                  >
                    Abrir WhatsApp Web
                  </a>
                )}
              </div>
              <textarea
                readOnly
                value={inviteResult.whatsapp_message}
                className="mt-3 min-h-32 w-full rounded-md border border-emerald-100 bg-white p-3 text-xs text-slate-700"
              />
              <p className="mt-2 text-[11px] font-medium text-emerald-800">
                Envio automatico nao esta ativo nesta etapa. Use copiar/colar ou
                abra o WhatsApp Web com a mensagem preenchida.
              </p>
            </div>
          )}
        </section>

        <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
          Sessoes Recentes
        </h3>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="divide-y divide-slate-100">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="flex cursor-pointer items-center justify-between p-4 transition-colors hover:bg-slate-50"
                onClick={() => nav("/history")}
              >
                <div>
                  <p className="text-sm font-semibold text-slate-700">
                    Paciente Anonimo #{9821 + i}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {new Date(Date.now() - i * 86400000).toLocaleDateString(
                      "pt-BR",
                    )}{" "}
                    - Duracao 47min - IPM medio 62.4
                  </p>
                </div>
                <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-bold text-emerald-700">
                  Finalizada
                </span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};
