import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiUrl } from "../lib/api";
import { LgpdNotice } from "../components/legal/LgpdNotice";

type PaymentMode = "package" | "single";

interface InviteData {
  token: string;
  session_id: string;
  status: string;
  session_url?: string;
  patient_session_url?: string;
  patient_known: boolean;
  patient_name: string;
  patient_email: string;
  patient_phone: string;
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

const initialPatientForm = {
  name: "",
  email: "",
  phone: "",
  document: "",
  birth_date: "",
  password: "",
  password_confirm: "",
};

const initialConsent = {
  terms_of_use: false,
  privacy_policy: false,
  sensitive_data_processing: false,
  audio_video_processing: false,
  research_anonymized: false,
};

export const PatientInvitePage: React.FC = () => {
  const { token = "" } = useParams<{ token: string }>();
  const [invite, setInvite] = useState<InviteData | null>(null);
  const [patientForm, setPatientForm] = useState(initialPatientForm);
  const [consent, setConsent] = useState(initialConsent);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState(false);
  const sessionEntryUrl =
    invite?.session_url ||
    invite?.patient_session_url ||
    (invite?.session_id
      ? `#/paciente/sessao/${invite.session_id}?invite=${token}`
      : "");

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch(apiUrl(`/api/session-invites/${token}`))
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Convite invalido.");
        return data;
      })
      .then((data: InviteData) => {
        if (!active) return;
        setInvite(data);
        setPatientForm((prev) => ({
          ...prev,
          name: data.patient_name || "",
          email: data.patient_email || "",
          phone: data.patient_phone || "",
        }));
        setAccepted(data.status === "accepted");
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Convite nao encontrado.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  const updatePatient = (key: keyof typeof initialPatientForm, value: string) => {
    setPatientForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateConsent = (key: keyof typeof initialConsent, value: boolean) => {
    setConsent((prev) => ({ ...prev, [key]: value }));
  };

  const submitAcceptance = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    if (!patientForm.document.trim()) {
      setError("Informe o CPF/documento do paciente.");
      setSubmitting(false);
      return;
    }
    if (patientForm.password.length < 8) {
      setError("A senha do paciente deve ter no minimo 8 caracteres.");
      setSubmitting(false);
      return;
    }
    if (patientForm.password !== patientForm.password_confirm) {
      setError("A confirmacao de senha nao confere.");
      setSubmitting(false);
      return;
    }
    const patientPayload: Omit<typeof patientForm, "password_confirm"> = {
      name: patientForm.name,
      email: patientForm.email,
      phone: patientForm.phone,
      document: patientForm.document,
      birth_date: patientForm.birth_date,
      password: patientForm.password,
    };
    try {
      const response = await fetch(apiUrl(`/api/session-invites/${token}/accept`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...patientPayload,
          consent,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Nao foi possivel confirmar.");
      if (data?.patient_portal_token) {
        localStorage.setItem("froid_patient_token", data.patient_portal_token);
        localStorage.setItem("froid_patient_user", JSON.stringify(data.patient || {}));
      }
      setInvite(data);
      setAccepted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao confirmar convite.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
        Carregando convite FROID...
      </div>
    );
  }

  if (error && !invite) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900/40 bg-slate-900 p-6">
          <p className="text-sm font-bold text-red-300">Convite indisponivel</p>
          <p className="mt-2 text-sm text-slate-300">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-3xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm">
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-xl font-bold text-slate-950">
            Convite para sessao clinica
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Confirme seus dados e os consentimentos antes da sessao.
          </p>
        </div>

        {invite && (
          <div className="mb-5 rounded-lg border border-blue-800 bg-blue-950 p-4 text-sm">
            <div className="grid gap-2 md:grid-cols-2">
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  Paciente
                </span>
                <strong>{invite.patient_name}</strong>
              </div>
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  Sessao
                </span>
                <strong>{invite.session_id}</strong>
              </div>
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  Pagamento
                </span>
                <strong>
                  {invite.payment.mode === "package"
                    ? `Pacote com ${invite.payment.package_sessions} sessoes`
                    : "Sessao avulsa"}
                </strong>
                <p className="mt-1 text-xs text-slate-300">
                  Valor da sessao: {invite.payment.session_value_brl}
                  {invite.payment.mode === "package"
                    ? ` | Total: ${invite.payment.package_total_brl}`
                    : ""}
                </p>
              </div>
              {invite.payment.mode === "single" && (
                <div>
                  <span className="block text-[10px] font-bold uppercase text-blue-200">
                    PIX
                  </span>
                  <code className="block max-h-16 overflow-y-auto rounded bg-slate-950 p-2 text-[10px] text-slate-300">
                    {invite.payment.pix_code}
                  </code>
                </div>
              )}
            </div>
          </div>
        )}

        {accepted ? (
          <div className="rounded-lg border border-emerald-100 bg-emerald-950/40 p-5">
            <p className="text-base font-bold text-emerald-900">
              Convite confirmado
            </p>
            <p className="mt-2 text-sm text-emerald-800">
              Seu cadastro e consentimento foram registrados. A sessao esta
              liberada para entrada do paciente.
            </p>
            {sessionEntryUrl && (
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href={sessionEntryUrl}
                  className="inline-flex rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-800"
                >
                  Entrar na sessao
                </a>
                <a
                  href="/app/#/paciente"
                  className="inline-flex rounded-lg border border-emerald-700 px-4 py-2 text-sm font-bold text-emerald-100 hover:bg-emerald-900"
                >
                  Portal do paciente
                </a>
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={submitAcceptance} className="space-y-5">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-xs font-semibold text-slate-300">
                Nome completo
                <input
                  value={patientForm.name}
                  onChange={(event) => updatePatient("name", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                CPF ou documento *
                <input
                  value={patientForm.document}
                  onChange={(event) =>
                    updatePatient("document", event.target.value)
                  }
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                E-mail
                <input
                  value={patientForm.email}
                  onChange={(event) => updatePatient("email", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                WhatsApp
                <input
                  value={patientForm.phone}
                  onChange={(event) => updatePatient("phone", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Data de nascimento
                <input
                  type="date"
                  value={patientForm.birth_date}
                  onChange={(event) =>
                    updatePatient("birth_date", event.target.value)
                  }
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Senha de acesso ao portal *
                <input
                  type="password"
                  value={patientForm.password}
                  onChange={(event) => updatePatient("password", event.target.value)}
                  minLength={8}
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Confirmar senha *
                <input
                  type="password"
                  value={patientForm.password_confirm}
                  onChange={(event) =>
                    updatePatient("password_confirm", event.target.value)
                  }
                  minLength={8}
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-950 p-4">
              <p className="text-sm font-bold text-slate-100">
                Consentimentos LGPD
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                O FROID trata dados pessoais e dados sensiveis de saude,
                incluindo audio, video, biomarcadores, transcricao e analises
                clinicas. O uso deve ocorrer para apoio ao profissional, com
                registro de consentimento e finalidade terapeutica.
              </p>
              <div className="mt-3">
                <LgpdNotice audience="patient" compact />
              </div>
              <div className="mt-3 space-y-2 text-xs text-slate-300">
                {[
                  ["terms_of_use", "Li e aceito as condicoes de utilizacao do FROID."],
                  ["privacy_policy", "Li e aceito a politica de privacidade."],
                  [
                    "sensitive_data_processing",
                    "Autorizo o tratamento de dados sensiveis de saude para esta sessao.",
                  ],
                  [
                    "audio_video_processing",
                    "Autorizo a captura e processamento de audio, video e biomarcadores.",
                  ],
                  [
                    "research_anonymized",
                    "Autorizo uso anonimizado para pesquisa e melhoria do FROID.",
                  ],
                ].map(([key, label]) => (
                  <label key={key} className="flex gap-2">
                    <input
                      type="checkbox"
                      checked={consent[key as keyof typeof initialConsent]}
                      onChange={(event) =>
                        updateConsent(
                          key as keyof typeof initialConsent,
                          event.target.checked,
                        )
                      }
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>

            {error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Confirmando..." : "Confirmar cadastro e convite"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
};


