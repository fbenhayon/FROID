import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiUrl } from "../lib/api";
import { LgpdNotice } from "../components/legal/LgpdNotice";
import { normalizeSessionLocale, patientCopy, type SessionLocale } from "../lib/localization";

type PaymentMode = "package" | "single";

interface InviteData {
  token: string;
  session_id: string;
  status: string;
  session_url?: string;
  patient_session_url?: string;
  patient_known: boolean;
  password_only?: boolean;
  patient_name: string;
  patient_email: string;
  patient_phone: string;
  patient_ui_locale?: SessionLocale;
  spoken_language?: SessionLocale;
  analysis_language?: SessionLocale;
  report_locale?: SessionLocale;
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

// Fase de testes: cadastro do paciente reduzido ao essencial.
const initialPatientForm = {
  name: "",
  email: "",
  phone: "",
  sex: "",
  birth_date: "",
  password: "",
  password_confirm: "",
};

const SEX_COPY: Record<string, { label: string; female: string; male: string; other: string; prefer: string }> = {
  "pt-BR": { label: "Sexo", female: "Feminino", male: "Masculino", other: "Outro", prefer: "Prefiro não informar" },
  "en-US": { label: "Sex", female: "Female", male: "Male", other: "Other", prefer: "Prefer not to say" },
  "fr-FR": { label: "Sexe", female: "Féminin", male: "Masculin", other: "Autre", prefer: "Préfère ne pas répondre" },
  "es-ES": { label: "Sexo", female: "Femenino", male: "Masculino", other: "Otro", prefer: "Prefiero no decirlo" },
};

export const PatientInvitePage: React.FC = () => {
  const { token = "" } = useParams<{ token: string }>();
  const [invite, setInvite] = useState<InviteData | null>(null);
  const [patientForm, setPatientForm] = useState(initialPatientForm);
  // Consentimento unico: um clique cobre TCLE, Termos, Privacidade e o
  // tratamento de dados sensiveis (audio/video). O uso de dados no data-froid
  // (pesquisa anonimizada) nao e mais solicitado nesta fase.
  const [consentAll, setConsentAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [uiLocale, setUiLocale] = useState<SessionLocale>(() =>
    normalizeSessionLocale(typeof navigator === "undefined" ? "" : navigator.language),
  );
  const copy = patientCopy(uiLocale);
  const sexCopy = SEX_COPY[uiLocale] || SEX_COPY["pt-BR"];
  const sessionEntryUrl =
    invite?.session_url ||
    invite?.patient_session_url ||
    (invite?.session_id
      ? `#/paciente/sessao/${invite.session_id}?invite=${token}`
      : "");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setInvite(null);
    setPatientForm({ ...initialPatientForm });
    setConsentAll(false);
    setAccepted(false);
    setSubmitting(false);
    setError("");
    const previousInviteToken = sessionStorage.getItem("froid_patient_invite_token") || "";
    if (previousInviteToken !== token) {
      sessionStorage.removeItem("froid_patient_token");
      sessionStorage.removeItem("froid_patient_user");
    }
    sessionStorage.setItem("froid_patient_invite_token", token);
    fetch(apiUrl(`/api/session-invites/${token}`))
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Convite inválido.");
        return data;
      })
      .then((data: InviteData) => {
        if (!active) return;
        const nextLocale = normalizeSessionLocale(data.patient_ui_locale, uiLocale);
        setUiLocale(nextLocale);
        document.documentElement.lang = nextLocale;
        setInvite(data);
        setPatientForm({
          ...initialPatientForm,
          name: data.patient_name || "",
          email: data.patient_email || "",
          phone: data.patient_phone || "",
        });
        setAccepted(data.status === "accepted");
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Convite não encontrado.");
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


  const submitAcceptance = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const passwordOnly = Boolean(invite?.password_only);
    // Senha obrigatoria em ambos os fluxos (novo cadastro e paciente recorrente).
    if (patientForm.password.length < 8) {
      setError(copy.errors.passwordLength);
      setSubmitting(false);
      return;
    }
    if (!passwordOnly && patientForm.password !== patientForm.password_confirm) {
      setError(copy.errors.passwordMatch);
      setSubmitting(false);
      return;
    }
    if (!passwordOnly && !patientForm.email.trim()) {
      setError(copy.errors.email);
      setSubmitting(false);
      return;
    }
    if (!passwordOnly && !consentAll) {
      setError(copy.errors.consent || "É necessário aceitar as autorizações para continuar.");
      setSubmitting(false);
      return;
    }
    // Um clique cobre todas as autorizações obrigatórias (sem data-froid).
    const consent = {
      patient_tcle: consentAll,
      terms_of_use: consentAll,
      privacy_policy: consentAll,
      sensitive_data_processing: consentAll,
      audio_video_processing: consentAll,
    };
    const patientPayload = {
      name: patientForm.name,
      email: patientForm.email,
      phone: patientForm.phone,
      sex: patientForm.sex,
      birth_date: patientForm.birth_date,
      password: patientForm.password,
    };
    try {
      const response = await fetch(apiUrl(`/api/session-invites/${token}/accept`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(passwordOnly
            ? { password: patientForm.password }
            : { ...patientPayload, consent }),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || copy.errors.confirmation);
      if (data?.patient_portal_token) {
        sessionStorage.setItem("froid_patient_token", data.patient_portal_token);
        sessionStorage.setItem("froid_patient_user", JSON.stringify(data.patient || {}));
      }
      setInvite(data);
      setAccepted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.errors.confirmation);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
        {copy.loadingInvite}
      </div>
    );
  }

  if (error && !invite) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-xl border border-red-900/40 bg-slate-900 p-6">
          <p className="text-sm font-bold text-red-300">{copy.unavailableInvite}</p>
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
          <h1 className="mt-2 text-xl font-bold text-slate-100">
            {copy.invitationTitle}
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            {copy.invitationSubtitle}
          </p>
          {uiLocale !== "pt-BR" && (
            <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-amber-300">
              {copy.pilotNotice}
            </p>
          )}
        </div>

        {invite && (
          <div className="mb-5 rounded-lg border border-blue-800 bg-blue-950 p-4 text-sm">
            <div className="grid gap-2 md:grid-cols-2">
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  {copy.patient}
                </span>
                <strong>{invite.patient_name}</strong>
              </div>
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  {copy.session}
                </span>
                <strong>{invite.session_id}</strong>
              </div>
              <div>
                <span className="block text-[10px] font-bold uppercase text-blue-200">
                  {copy.payment}
                </span>
                <strong>
                  {invite.payment.mode === "package"
                    ? copy.packageLabel(invite.payment.package_sessions)
                    : copy.singleSession}
                </strong>
                <p className="mt-1 text-xs text-slate-300">
                  {copy.sessionValue}: {invite.payment.session_value_brl}
                  {invite.payment.mode === "package"
                    ? ` | ${copy.total}: ${invite.payment.package_total_brl}`
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
            <p className="text-base font-bold text-emerald-100">
              {copy.confirmed}
            </p>
            <p className="mt-2 text-sm text-emerald-200">
              {copy.confirmedBody}
            </p>
            {sessionEntryUrl && (
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href={sessionEntryUrl}
                  className="inline-flex rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-800"
                >
                  {copy.enterSession}
                </a>
                <a
                  href="/app/#/paciente"
                  className="inline-flex rounded-lg border border-emerald-700 px-4 py-2 text-sm font-bold text-emerald-100 hover:bg-emerald-900"
                >
                  {copy.patientPortal}
                </a>
              </div>
            )}
          </div>
        ) : (
          <form
            autoComplete="off"
            onSubmit={submitAcceptance}
            className="space-y-5 [&_input]:border-blue-800 [&_input]:bg-blue-950 [&_input]:text-white [&_input]:placeholder:text-blue-300 [&_input]:focus:border-cyan-400"
          >
            {invite?.password_only ? (
              <div className="rounded-lg border border-cyan-800 bg-cyan-950/40 p-4">
                <p className="text-sm font-bold text-cyan-100">
                  {copy.accountLocated}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-300">
                  {copy.accountLocatedBody}
                </p>
                <label className="mt-4 block text-xs font-semibold text-slate-200">
                  {copy.accessPassword} *
                  <input
                    type="password"
                    value={patientForm.password}
                    onChange={(event) => updatePatient("password", event.target.value)}
                    minLength={8}
                    required
                    autoComplete="current-password"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                  />
                </label>
              </div>
            ) : (
              <>
              <div className="grid gap-3 md:grid-cols-2">
              <label className="text-xs font-semibold text-slate-300">
                {copy.fullName} *
                <input
                  value={patientForm.name}
                  onChange={(event) => updatePatient("name", event.target.value)}
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                {copy.phone}
                <input
                  value={patientForm.phone}
                  onChange={(event) => updatePatient("phone", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                {copy.email} *
                <input
                  value={patientForm.email}
                  onChange={(event) => updatePatient("email", event.target.value)}
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                {sexCopy.label}
                <select
                  value={patientForm.sex}
                  onChange={(event) => updatePatient("sex", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
                >
                  <option value="">—</option>
                  <option value="F">{sexCopy.female}</option>
                  <option value="M">{sexCopy.male}</option>
                  <option value="O">{sexCopy.other}</option>
                  <option value="N">{sexCopy.prefer}</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-300">
                {copy.birthDate}
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
                {copy.portalPassword} *
                <input
                  type="password"
                  autoComplete="new-password"
                  value={patientForm.password}
                  onChange={(event) => updatePatient("password", event.target.value)}
                  minLength={8}
                  required
                  className="mt-1 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                {copy.confirmPassword} *
                <input
                  type="password"
                  autoComplete="new-password"
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
                {copy.privacyAuthorizations}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                {copy.privacyBody}
              </p>
              <p className="mt-2 text-xs font-bold text-cyan-300">
                <a className="underline" href="#/tcle-paciente" target="_blank" rel="noreferrer">TCLE integral</a>
                {" · "}
                <a className="underline" href="#/privacidade" target="_blank" rel="noreferrer">Política de Privacidade</a>
                {" · "}
                <a className="underline" href="#/termos" target="_blank" rel="noreferrer">Termos de Uso</a>
              </p>
              <div className="mt-3">
                <LgpdNotice audience="patient" compact locale={uiLocale} />
              </div>
              <div className="mt-3 text-xs text-slate-300">
                <label className="flex gap-2">
                  <input
                    type="checkbox"
                    checked={consentAll}
                    onChange={(event) => setConsentAll(event.target.checked)}
                  />
                  <span>
                    {{
                      "pt-BR": "Li e aceito o TCLE, os Termos de Uso e a Política de Privacidade, e autorizo o tratamento dos meus dados sensíveis (áudio e vídeo) para a realização da sessão.",
                      "en-US": "I have read and accept the Informed Consent (TCLE), the Terms of Use and the Privacy Policy, and I authorize the processing of my sensitive data (audio and video) to run the session.",
                      "fr-FR": "J'ai lu et j'accepte le consentement éclairé (TCLE), les Conditions d'utilisation et la Politique de confidentialité, et j'autorise le traitement de mes données sensibles (audio et vidéo) pour la réalisation de la séance.",
                      "es-ES": "He leído y acepto el TCLE, los Términos de Uso y la Política de Privacidad, y autorizo el tratamiento de mis datos sensibles (audio y vídeo) para la realización de la sesión.",
                    }[uiLocale] ||
                      "Li e aceito o TCLE, os Termos de Uso e a Política de Privacidade, e autorizo o tratamento dos meus dados sensíveis (áudio e vídeo) para a realização da sessão."}
                  </span>
                </label>
              </div>
            </div>
              </>
            )}

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
              {submitting
                ? copy.confirming
                : invite?.password_only
                  ? copy.confirmPasswordEntry
                  : copy.confirmRegistration}
            </button>
          </form>
        )}
      </main>
    </div>
  );
};
