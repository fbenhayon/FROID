import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiUrl, publicAppUrl } from "../lib/api";
import { rememberSessionPatient } from "../lib/session-report";
import { LgpdNotice } from "../components/legal/LgpdNotice";

type PaymentMode = "package" | "single";

interface InviteResult {
  token: string;
  session_id: string;
  invite_url: string;
  whatsapp_url: string;
  whatsapp_message: string;
  patient_id?: string;
  patient_known: boolean;
  payment: {
    mode: PaymentMode;
    package_sessions: number;
    session_value_brl: string;
    package_total_brl: string;
    pix_code: string;
    payment_status: string;
  };
}

interface SessionEvent {
  id: number;
  type: "invite_created" | "invite_opened" | "invite_accepted" | "patient_joined";
  session_id: string;
  patient_name?: string;
  created_at: string;
}

const initialForm = {
  patient_name: "",
  patient_email: "",
  patient_phone: "",
  payment_mode: "single" as PaymentMode,
  session_value: "",
  package_sessions: "4",
  pix_code: "",
};

function makeId() {
  return `froid-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export const NewPatient: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState(() => ({
    ...initialForm,
    patient_name: searchParams.get("name") || "",
    patient_email: searchParams.get("email") || "",
    patient_phone: searchParams.get("phone") || "",
  }));
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [invite, setInvite] = useState<InviteResult | null>(null);
  const [patientActivity, setPatientActivity] = useState("");
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const inviteBaseUrl = useMemo(() => publicAppUrl(), []);

  const updateForm = (key: keyof typeof initialForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard?.writeText(text);
    } catch {
      window.prompt("Copie o conteudo abaixo:", text);
    }
  };

  const createInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setError("");
    setInvite(null);

    try {
      const response = await fetch(apiUrl("/api/session-invites"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          session_id: makeId(),
          base_url: inviteBaseUrl,
          package_sessions: Number(form.package_sessions || 0),
          session_value: form.session_value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Nao foi possivel criar o convite.");
      }
      setInvite(data);
      rememberSessionPatient(data.session_id, {
        id: data.patient_id,
        name: form.patient_name,
        email: form.patient_email,
        phone: form.patient_phone,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar convite.");
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    if (!invite?.session_id) return;
    let active = true;
    redirectingRef.current = false;

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
        const sessionEvents = events.filter(
          (event) => event.session_id === invite.session_id,
        );
        const latest = sessionEvents[sessionEvents.length - 1];
        if (!latest || !active) return;
        const patient = latest.patient_name || form.patient_name || "Paciente";
        if (latest.type === "invite_opened") {
          setPatientActivity(`${patient} abriu o link de cadastro FROID.`);
        }
        if (latest.type === "invite_accepted") {
          setPatientActivity(`${patient} confirmou cadastro e consentimentos LGPD.`);
        }
        if (latest.type === "patient_joined" && !redirectingRef.current) {
          setPatientActivity(`${patient} entrou na sessao. Abrindo sala do profissional...`);
          rememberSessionPatient(invite.session_id, {
            id: invite.patient_id,
            name: patient,
            email: form.patient_email,
            phone: form.patient_phone,
          });
          redirectingRef.current = true;
          window.setTimeout(() => {
            if (active) navigate(`/session/${invite.session_id}`);
          }, 700);
        }
      } catch {
        // Polling best-effort.
      }
    };

    void pollSessionEvents();
    const intervalId = window.setInterval(pollSessionEvents, 2500);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [form.patient_email, form.patient_name, form.patient_phone, invite, navigate]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-600">
              Cadastro de Paciente
            </p>
            <h1 className="text-xl font-bold text-slate-900">
              Novo paciente e convite LGPD
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Gere o link publico para cadastro, consentimentos e entrada na sessao.
            </p>
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
          >
            Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-4 p-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-bold text-slate-900">
            Dados iniciais e pagamento
          </h2>
          <form onSubmit={createInvite} className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="text-xs font-bold text-slate-700">
              Nome do paciente
              <input
                value={form.patient_name}
                onChange={(event) => updateForm("patient_name", event.target.value)}
                className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>
            <label className="text-xs font-bold text-slate-700">
              WhatsApp
              <input
                value={form.patient_phone}
                onChange={(event) => updateForm("patient_phone", event.target.value)}
                className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>
            <label className="text-xs font-bold text-slate-700">
              E-mail
              <input
                value={form.patient_email}
                onChange={(event) => updateForm("patient_email", event.target.value)}
                className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>
            <label className="text-xs font-bold text-slate-700">
              Forma de pagamento
              <select
                value={form.payment_mode}
                onChange={(event) =>
                  updateForm("payment_mode", event.target.value as PaymentMode)
                }
                className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
              >
                <option value="single">Sessao avulsa com PIX</option>
                <option value="package">Pacote de sessoes</option>
              </select>
            </label>
            <label className="text-xs font-bold text-slate-700">
              Valor da sessao (R$)
              <input
                value={form.session_value}
                onChange={(event) => updateForm("session_value", event.target.value)}
                className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>
            {form.payment_mode === "package" ? (
              <label className="text-xs font-bold text-slate-700">
                Numero de sessoes
                <input
                  type="number"
                  min={1}
                  value={form.package_sessions}
                  onChange={(event) =>
                    updateForm("package_sessions", event.target.value)
                  }
                  className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
                />
              </label>
            ) : (
              <label className="text-xs font-bold text-slate-700">
                Codigo PIX copia e cola
                <input
                  value={form.pix_code}
                  onChange={(event) => updateForm("pix_code", event.target.value)}
                  className="mt-1 w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 font-normal outline-none focus:border-blue-400 focus:bg-white"
                />
              </label>
            )}
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={creating}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? "Gerando..." : "Gerar link de cadastro"}
              </button>
              {error && (
                <p className="mt-2 rounded bg-red-50 px-3 py-2 text-xs font-bold text-red-700">
                  {error}
                </p>
              )}
            </div>
          </form>
        </section>

        <aside className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-xs text-blue-950">
          <h2 className="text-sm font-bold">Fluxo do paciente</h2>
          <p className="mt-2 leading-relaxed">
            O paciente recebe o link, confirma dados, aceita LGPD e entra na sala.
            O cadastro definitivo acontece no aceite do convite.
          </p>
          {patientActivity && (
            <p className="mt-3 rounded border border-emerald-100 bg-emerald-50 p-2 font-bold text-emerald-800">
              {patientActivity}
            </p>
          )}
          <p className="mt-2 rounded border border-blue-100 bg-white p-2 font-mono text-[11px] text-blue-800">
            Base publica: {inviteBaseUrl}
          </p>
          <div className="mt-3">
            <LgpdNotice audience="professional" compact />
          </div>
          {invite ? (
            <div className="mt-4 space-y-3">
              <p className="font-bold">
                Convite criado: {invite.session_id} |{" "}
                {invite.patient_known ? "paciente cadastrado" : "novo cadastro"}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => copyText(invite.whatsapp_message)}
                  className="rounded border border-blue-200 bg-white px-2 py-1 font-bold text-blue-700 hover:bg-blue-50"
                >
                  Copiar mensagem
                </button>
                <button
                  onClick={() => copyText(invite.invite_url)}
                  className="rounded border border-blue-200 bg-white px-2 py-1 font-bold text-blue-700 hover:bg-blue-50"
                >
                  Copiar link
                </button>
                <button
                  onClick={() => navigate(`/session/${invite.session_id}`)}
                  className="rounded border border-blue-200 bg-white px-2 py-1 font-bold text-blue-700 hover:bg-blue-50"
                >
                  Abrir sala DR
                </button>
              </div>
              <textarea
                readOnly
                value={invite.whatsapp_message}
                className="h-44 w-full rounded border border-blue-100 bg-white p-2 text-slate-700"
              />
            </div>
          ) : (
            <p className="mt-4 rounded border border-blue-100 bg-white p-3 text-blue-800">
              Preencha os dados para gerar o link de cadastro do paciente.
            </p>
          )}
        </aside>
      </main>
    </div>
  );
};
