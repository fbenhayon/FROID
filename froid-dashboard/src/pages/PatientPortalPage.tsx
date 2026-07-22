import React, { useCallback, useEffect, useMemo, useState } from "react";
import { apiUrl } from "../lib/api";
import {
  fmt,
  formatDateTime,
  sessionMetricCells,
  sessionResultText,
} from "../lib/patient-dashboard";
import type { PatientIdentity, SessionReportRecord } from "../lib/session-report";
import { formatDuration } from "../lib/session-report";

const PATIENT_TOKEN_KEY = "froid_patient_token";
const PATIENT_USER_KEY = "froid_patient_user";

type PatientPortalResponse = {
  patient: PatientIdentity;
  reports: SessionReportRecord[];
  total: number;
};

type PrivacyRequest = {
  id: string;
  organization_name: string;
  request_type: string;
  status: string;
  submitted_at: string;
  service_due_at: string;
  response_summary?: string;
  legal_basis?: string;
  retention_exception?: string;
};

type PrivacyOverview = {
  organizations: Array<{ organization_id: string; organization_name: string }>;
  requests: PrivacyRequest[];
  rights: string[];
  processing: { categories: string[]; automated_decision: boolean };
};

type ConsentPreferences = {
  patient_tcle: boolean;
  terms_of_use: boolean;
  privacy_policy: boolean;
  sensitive_data_processing: boolean;
  audio_video_processing: boolean;
  research_anonymized: boolean;
};

type ConsentOverview = {
  consent: ConsentPreferences;
  version: string;
  updated_at: string;
  session_authorization_active: boolean;
};

const PRIVACY_RIGHT_LABELS: Record<string, string> = {
  access: "Acesso aos dados",
  correction: "Correção",
  portability: "Portabilidade",
  processing_information: "Informações sobre o tratamento",
  consent_withdrawal: "Revogação de consentimento",
  restriction: "Bloqueio ou restrição",
  deletion: "Eliminação",
  anonymization: "Anonimização",
  automated_review: "Revisão de processamento automatizado",
};

function readStoredPatient() {
  if (typeof window === "undefined") return null;
  try {
    window.localStorage.removeItem(PATIENT_USER_KEY);
    const raw = window.sessionStorage.getItem(PATIENT_USER_KEY);
    return raw ? (JSON.parse(raw) as PatientIdentity) : null;
  } catch {
    return null;
  }
}

function metricValue(snapshot: SessionReportRecord["sessionAverage"] | undefined, key: string) {
  if (!snapshot) return "--";
  const cell = sessionMetricCells(snapshot).find((item) => item.key === key);
  return cell?.value || "--";
}

function savePatientDownload(report: SessionReportRecord) {
  const sessionId = report.sessionId || report.id || "sessão";
  const blob = new Blob([JSON.stringify(report, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `froid-resultado-${sessionId}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function saveAllPatientDownloads(patient: PatientIdentity | null, reports: SessionReportRecord[]) {
  const payload = {
    exportedAt: new Date().toISOString(),
    patient,
    reports,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "froid-resultados-paciente.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const PatientPortalPage: React.FC = () => {
  const [token, setToken] = useState(() => {
    if (typeof window === "undefined") return "";
    window.localStorage.removeItem(PATIENT_TOKEN_KEY);
    return window.sessionStorage.getItem(PATIENT_TOKEN_KEY) || "";
  });
  const [patient, setPatient] = useState<PatientIdentity | null>(() => readStoredPatient());
  const [reports, setReports] = useState<SessionReportRecord[]>([]);
  const [loginForm, setLoginForm] = useState({ document: "", password: "" });
  const [profileForm, setProfileForm] = useState({
    name: "",
    phone: "",
    document: "",
    birth_date: "",
  });
  const [expandedSession, setExpandedSession] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyOverview | null>(null);
  const [privacyForm, setPrivacyForm] = useState({
    request_type: "access",
    organization_id: "",
    details: "",
  });
  const [privacySaving, setPrivacySaving] = useState(false);
  const [consentOverview, setConsentOverview] = useState<ConsentOverview | null>(null);
  const [consentForm, setConsentForm] = useState<ConsentPreferences>({
    patient_tcle: false,
    terms_of_use: false,
    privacy_policy: false,
    sensitive_data_processing: false,
    audio_video_processing: false,
    research_anonymized: false,
  });
  const [consentSaving, setConsentSaving] = useState(false);

  const authHeaders = useMemo<Record<string, string>>(() => {
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }, [token]);

  const applyPatient = useCallback((nextPatient: PatientIdentity | null) => {
    setPatient(nextPatient);
    setProfileForm({
      name: nextPatient?.name || "",
      phone: nextPatient?.phone || "",
      document: nextPatient?.document || "",
      birth_date: (nextPatient as PatientIdentity & { birth_date?: string })?.birth_date || "",
    });
    if (typeof window !== "undefined") {
      if (nextPatient) {
        window.sessionStorage.setItem(PATIENT_USER_KEY, JSON.stringify(nextPatient));
      } else {
        window.sessionStorage.removeItem(PATIENT_USER_KEY);
      }
    }
  }, []);

  const loadReports = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl("/api/patient-portal/reports"), {
        headers: authHeaders,
      });
      const data: PatientPortalResponse = await response.json();
      if (!response.ok) throw new Error((data as any)?.detail || "Não foi possível carregar os resultados.");
      applyPatient(data.patient || null);
      setReports(Array.isArray(data.reports) ? data.reports : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar o portal do paciente.");
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, [applyPatient, authHeaders, token]);

  const loadPrivacy = useCallback(async () => {
    if (!token) return;
    const response = await fetch(apiUrl("/api/patient-portal/privacy"), {
      headers: authHeaders,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data?.detail || "Não foi possível carregar seus direitos LGPD.");
    setPrivacy(data as PrivacyOverview);
  }, [authHeaders, token]);

  const loadConsent = useCallback(async () => {
    if (!token) return;
    const response = await fetch(apiUrl("/api/patient-portal/consent"), {
      headers: authHeaders,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data?.detail || "Não foi possível carregar suas autorizações.");
    setConsentOverview(data as ConsentOverview);
    setConsentForm({ ...(data as ConsentOverview).consent, patient_tcle: Boolean((data as ConsentOverview).consent.patient_tcle) });
  }, [authHeaders, token]);

  useEffect(() => {
    if (!token) return;
    fetch(apiUrl("/api/patient-auth/me"), { headers: authHeaders })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Sessão expirada.");
        applyPatient(data.patient || null);
        return Promise.all([
          loadReports(),
          loadConsent(),
          loadPrivacy().catch((err) => {
            setPrivacy(null);
            setError(err instanceof Error ? err.message : "Portal LGPD temporariamente indisponível.");
          }),
        ]);
      })
      .catch(() => {
        if (typeof window !== "undefined") {
          window.sessionStorage.removeItem(PATIENT_TOKEN_KEY);
          window.sessionStorage.removeItem(PATIENT_USER_KEY);
        }
        setToken("");
        applyPatient(null);
      });
  }, [applyPatient, authHeaders, loadConsent, loadPrivacy, loadReports, token]);

  const saveConsent = async (event: React.FormEvent) => {
    event.preventDefault();
    setConsentSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(apiUrl("/api/patient-portal/consent"), {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(consentForm),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível atualizar suas autorizações.");
      setConsentOverview(data as ConsentOverview);
      setConsentForm({ ...(data as ConsentOverview).consent, patient_tcle: Boolean((data as ConsentOverview).consent.patient_tcle) });
      setMessage("Autorizações atualizadas e registradas.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar autorizações.");
    } finally {
      setConsentSaving(false);
    }
  };

  const submitPrivacyRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setPrivacySaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(apiUrl("/api/patient-portal/privacy/requests"), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(privacyForm),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível protocolar a solicitação.");
      setPrivacyForm((current) => ({ ...current, details: "" }));
      await loadPrivacy();
      setMessage(`Solicitação protocolada para ${data.total || 1} organização(ões).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao protocolar solicitação LGPD.");
    } finally {
      setPrivacySaving(false);
    }
  };

  const downloadPrivacyExport = async () => {
    setError("");
    try {
      const response = await fetch(apiUrl("/api/patient-portal/privacy/export"), {
        headers: authHeaders,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível preparar a exportação.");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "froid-exportacao-lgpd.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar dados LGPD.");
    }
  };

  const login = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(apiUrl("/api/patient-auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível acessar o portal.");
      const nextToken = data.token || "";
      setToken(nextToken);
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(PATIENT_TOKEN_KEY, nextToken);
      }
      applyPatient(data.patient || null);
      setMessage("Acesso do paciente liberado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao autenticar paciente.");
    } finally {
      setLoading(false);
    }
  };

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(apiUrl("/api/patient-portal/profile"), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify(profileForm),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível salvar seus dados.");
      applyPatient(data.patient || null);
      setMessage("Dados do paciente atualizados.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar cadastro.");
    } finally {
      setSaving(false);
    }
  };

  const logout = () => {
    if (token) {
      fetch(apiUrl("/api/patient-auth/logout"), {
        method: "POST",
        headers: authHeaders,
      }).catch(() => undefined);
    }
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(PATIENT_TOKEN_KEY);
      window.sessionStorage.removeItem(PATIENT_USER_KEY);
    }
    setToken("");
    applyPatient(null);
    setReports([]);
    setPrivacy(null);
    setConsentOverview(null);
    setMessage("");
    setError("");
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <header className="border-b border-slate-800 bg-slate-950 px-6 py-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            Portal do paciente
          </p>
          <h1 className="mt-2 text-2xl font-black text-white">Acesso aos seus resultados FROID</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-300">
            Entre para consultar suas sessões, gerenciar seus dados cadastrais e baixar seus
            resultados registrados na plataforma.
          </p>
        </header>
        <main className="mx-auto grid max-w-5xl gap-4 px-4 py-8 md:grid-cols-[1fr_0.85fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-lg font-black text-white">Seus dados pertencem a você</h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              O FROID disponibiliza ao paciente uma area própria para consultar os resultados
              das sessões finalizadas, conferir dados pessoais e baixar os registros autorizados.
              O acesso exige CPF/documento e senha criados no cadastro LGPD para proteger suas informações.
            </p>
            <div className="mt-5 grid gap-3 text-xs text-slate-300 sm:grid-cols-3">
              {[
                ["Resultados", "Métricas, cortes, resumos e dissonâncias da sessão."],
                ["Cadastro", "Atualização de telefone, documento e dados básicos."],
                ["Download", "Exportacao do resultado em arquivo JSON para guarda pessoal."],
              ].map(([title, detail]) => (
                <div key={title} className="rounded border border-slate-700 bg-slate-950 p-3">
                  <p className="font-black text-cyan-200">{title}</p>
                  <p className="mt-2 leading-5">{detail}</p>
                </div>
              ))}
            </div>
          </section>

          <form onSubmit={login} className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-base font-black text-white">Login do paciente</h2>
            <p className="mt-1 text-xs text-slate-400">
              Informe CPF/documento e senha cadastrados no aceite do convite.
            </p>
            <label className="mt-4 block text-xs font-bold text-slate-300">
              CPF ou documento
              <input
                value={loginForm.document}
                onChange={(event) => setLoginForm((prev) => ({ ...prev, document: event.target.value }))}
                required
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
              />
            </label>
            <label className="mt-3 block text-xs font-bold text-slate-300">
              Senha
              <input
                type="password"
                value={loginForm.password}
                onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
                minLength={8}
                required
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
              />
            </label>
            {error && <p className="mt-3 text-xs font-bold text-red-300">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="mt-4 w-full rounded bg-cyan-600 px-4 py-2 text-sm font-black text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Validando..." : "Entrar no portal"}
            </button>
          </form>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              Portal do paciente
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              {patient?.name || "Paciente FROID"}
            </h1>
            <p className="mt-1 text-sm text-slate-300">
              Resultados das sessões, dados cadastrais e downloads.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => loadReports()}
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              Atualizar
            </button>
            <button
              type="button"
              onClick={logout}
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-4 px-4 py-5 lg:grid-cols-[0.78fr_1.22fr]">
        <section className="space-y-4">
          <form onSubmit={saveProfile} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-black text-white">Meus dados</h2>
              <span className="rounded bg-slate-950 px-2 py-1 text-[10px] font-bold uppercase text-slate-400">
                LGPD
              </span>
            </div>
            <label className="mt-3 block text-[10px] font-bold uppercase text-slate-400">
              Nome
              <input
                value={profileForm.name}
                onChange={(event) => setProfileForm((prev) => ({ ...prev, name: event.target.value }))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm normal-case text-white outline-none focus:border-cyan-400"
              />
            </label>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block text-[10px] font-bold uppercase text-slate-400">
                Documento
                <input
                  value={profileForm.document}
                  onChange={(event) =>
                    setProfileForm((prev) => ({ ...prev, document: event.target.value }))
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm normal-case text-white outline-none focus:border-cyan-400"
                />
              </label>
              <label className="block text-[10px] font-bold uppercase text-slate-400">
                WhatsApp
                <input
                  value={profileForm.phone}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, phone: event.target.value }))}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm normal-case text-white outline-none focus:border-cyan-400"
                />
              </label>
              <label className="block text-[10px] font-bold uppercase text-slate-400">
                Nascimento
                <input
                  type="date"
                  value={profileForm.birth_date}
                  onChange={(event) =>
                    setProfileForm((prev) => ({ ...prev, birth_date: event.target.value }))
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm normal-case text-white outline-none focus:border-cyan-400"
                />
              </label>
              <label className="block text-[10px] font-bold uppercase text-slate-400">
                E-mail
                <input
                  value={patient?.email || ""}
                  readOnly
                  className="mt-1 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm normal-case text-slate-400"
                />
              </label>
            </div>
            <button
              type="submit"
              disabled={saving}
              className="mt-4 rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar dados"}
            </button>
          </form>

          <form onSubmit={saveConsent} className="rounded-lg border border-emerald-900 bg-slate-900 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-300">
                  Autorizações permanentes
                </p>
                <h2 className="mt-1 text-sm font-black text-white">
                  Participação nas sessões FROID
                </h2>
              </div>
              <span
                className={`rounded px-2 py-1 text-[10px] font-black uppercase ${
                  consentOverview?.session_authorization_active
                    ? "bg-emerald-950 text-emerald-200"
                    : "bg-amber-950 text-amber-200"
                }`}
              >
                {consentOverview?.session_authorization_active
                  ? "Sessões autorizadas"
                  : "Autorização incompleta"}
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-300">
              Estas escolhas acompanham seu cadastro. Nos próximos convites,
              você informará apenas sua senha. Desmarcar uma autorização
              obrigatória bloqueia novas sessões até uma nova alteração.
            </p>
            <div className="mt-3 space-y-2 text-xs text-slate-300">
              {[
                ["patient_tcle", "Li e aceito o TCLE vigente do FROID."],
                ["terms_of_use", "Aceito os termos de uso do FROID."],
                ["privacy_policy", "Aceito a política de privacidade."],
                ["sensitive_data_processing", "Autorizo o tratamento de dados sensíveis de saúde."],
                ["audio_video_processing", "Autorizo a captura e o processamento de áudio, vídeo e biomarcadores."],
                ["research_anonymized", "Autorizo o uso anonimizado para pesquisa e melhoria do FROID (opcional)."],
              ].map(([key, label]) => (
                <label key={key} className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={consentForm[key as keyof ConsentPreferences]}
                    onChange={(event) =>
                      setConsentForm((current) => ({
                        ...current,
                        [key]: event.target.checked,
                      }))
                    }
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <button
              type="submit"
              disabled={consentSaving}
              className="mt-4 rounded bg-emerald-700 px-4 py-2 text-xs font-black text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {consentSaving ? "Salvando..." : "Salvar autorizações"}
            </button>
          </form>

          <section className="rounded-lg border border-cyan-900 bg-slate-900 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">
                  Direitos do titular
                </p>
                <h2 className="mt-1 text-sm font-black text-white">Portal LGPD</h2>
              </div>
              <button
                type="button"
                onClick={downloadPrivacyExport}
                className="rounded border border-cyan-700 bg-cyan-950 px-3 py-2 text-[11px] font-black text-cyan-100 hover:bg-cyan-900"
              >
                Exportar meus dados
              </button>
            </div>

            <p className="mt-3 text-xs leading-5 text-slate-300">
              Consulte o tratamento realizado e protocole pedidos de acesso, correção,
              portabilidade, revisão, bloqueio, anonimização ou eliminação. Solicitações que
              envolvam registros clínicos passam por análise documentada da organização responsável.
            </p>

            <form onSubmit={submitPrivacyRequest} className="mt-4 rounded border border-slate-700 bg-slate-950 p-3">
              <label className="block text-[10px] font-bold uppercase text-slate-400">
                Direito que deseja exercer
                <select
                  value={privacyForm.request_type}
                  onChange={(event) =>
                    setPrivacyForm((current) => ({ ...current, request_type: event.target.value }))
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs normal-case text-white outline-none focus:border-cyan-400"
                >
                  {Object.entries(PRIVACY_RIGHT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>

              <label className="mt-3 block text-[10px] font-bold uppercase text-slate-400">
                Organização responsável
                <select
                  value={privacyForm.organization_id}
                  onChange={(event) =>
                    setPrivacyForm((current) => ({ ...current, organization_id: event.target.value }))
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs normal-case text-white outline-none focus:border-cyan-400"
                >
                  <option value="">Todas as organizações relacionadas</option>
                  {(privacy?.organizations || []).map((organization) => (
                    <option key={organization.organization_id} value={organization.organization_id}>
                      {organization.organization_name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="mt-3 block text-[10px] font-bold uppercase text-slate-400">
                Detalhes do pedido
                <textarea
                  value={privacyForm.details}
                  onChange={(event) =>
                    setPrivacyForm((current) => ({ ...current, details: event.target.value }))
                  }
                  maxLength={4000}
                  rows={3}
                  placeholder="Descreva o período, dado ou correção solicitada."
                  className="mt-1 w-full resize-y rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs normal-case text-white outline-none focus:border-cyan-400"
                />
              </label>

              <button
                type="submit"
                disabled={privacySaving || !(privacy?.organizations || []).length}
                className="mt-3 rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {privacySaving ? "Protocolando..." : "Protocolar solicitação"}
              </button>
            </form>

            <div className="mt-4 space-y-2">
              <p className="text-[10px] font-bold uppercase text-slate-400">Acompanhamento</p>
              {(privacy?.requests || []).map((item) => (
                <article key={item.id} className="rounded border border-slate-700 bg-slate-950 p-3 text-xs">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-black text-slate-100">
                        {PRIVACY_RIGHT_LABELS[item.request_type] || item.request_type}
                      </p>
                      <p className="mt-1 text-slate-400">{item.organization_name}</p>
                    </div>
                    <span className="rounded bg-slate-800 px-2 py-1 text-[10px] font-bold uppercase text-cyan-200">
                      {item.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="mt-2 text-[11px] text-slate-400">
                    Protocolo {item.id} · prazo operacional {formatDateTime(new Date(item.service_due_at))}
                  </p>
                  {item.response_summary && (
                    <p className="mt-2 rounded bg-slate-900 p-2 leading-5 text-slate-300">
                      {item.response_summary}
                    </p>
                  )}
                  {item.retention_exception && (
                    <p className="mt-2 text-[11px] text-amber-200">
                      Exceção de retenção: {item.retention_exception}
                    </p>
                  )}
                </article>
              ))}
              {!privacy?.requests?.length && (
                <p className="rounded border border-slate-800 bg-slate-950 p-3 text-xs text-slate-400">
                  Nenhuma solicitação LGPD protocolada.
                </p>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-black text-white">Resumo do paciente</h2>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded border border-slate-700 bg-slate-950 p-3">
                <p className="text-[10px] font-bold uppercase text-slate-400">Sessões</p>
                <p className="mt-1 text-xl font-black text-white">{reports.length}</p>
              </div>
              <div className="rounded border border-slate-700 bg-slate-950 p-3">
                <p className="text-[10px] font-bold uppercase text-slate-400">Downloads</p>
                <button
                  type="button"
                  onClick={() => saveAllPatientDownloads(patient, reports)}
                  disabled={!reports.length}
                  className="mt-2 rounded bg-slate-800 px-3 py-2 text-[11px] font-black text-slate-100 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Baixar todos
                </button>
              </div>
            </div>
            {message && <p className="mt-3 text-xs font-bold text-emerald-300">{message}</p>}
            {error && <p className="mt-3 text-xs font-bold text-red-300">{error}</p>}
          </section>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-black text-white">Resultados das sessões</h2>
              <p className="mt-1 text-xs text-slate-400">
                Registros mais recentes aparecem primeiro.
              </p>
            </div>
            {loading && <span className="text-xs font-bold text-cyan-300">Carregando...</span>}
          </div>

          {!reports.length ? (
            <div className="mt-4 rounded border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">
              Nenhum resultado de sessão finalizada foi localizado para este cadastro.
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {reports.map((report) => {
                const expanded = expandedSession === report.sessionId;
                const createdAt = report.createdAt ? new Date(report.createdAt) : new Date();
                const summary = sessionResultText(report, 70);
                return (
                  <article
                    key={report.sessionId || report.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-cyan-300">
                          {formatDateTime(createdAt)}
                        </p>
                        <h3 className="mt-1 text-sm font-black text-white">
                          {report.sessionSummary?.theme || report.sessionAverage?.theme || "Sessão FROID"}
                        </h3>
                        <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-300">{summary}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setExpandedSession(expanded ? "" : report.sessionId)}
                          className="rounded border border-slate-700 px-3 py-2 text-[11px] font-black text-slate-200 hover:bg-slate-800"
                        >
                          {expanded ? "Ocultar" : "Ver detalhes"}
                        </button>
                        <button
                          type="button"
                          onClick={() => savePatientDownload(report)}
                          className="rounded bg-cyan-700 px-3 py-2 text-[11px] font-black text-white hover:bg-cyan-600"
                        >
                          Baixar
                        </button>
                      </div>
                    </div>

                    <div className="mt-3 overflow-x-auto">
                      <table className="min-w-max table-auto text-left text-[10px] leading-tight">
                        <thead className="uppercase text-slate-400">
                          <tr>
                            {["Duração", "IPM", "IDM", "ZONAS", "Tom", "P/min", "Disso.", "MFCC7", "MFCC9"].map(
                              (label) => (
                                <th key={label} className="whitespace-nowrap border-l border-slate-700 px-2 py-1 first:border-l-0">
                                  {label}
                                </th>
                              ),
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="text-slate-200">
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 first:border-l-0">
                              {formatDuration(report.durationSeconds || 0)}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "ipm")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "idm")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "zone")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "tone")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "wpm")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "dissonance")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "mfcc7")}
                            </td>
                            <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                              {metricValue(report.sessionAverage, "mfcc9")}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {expanded && (
                      <div className="mt-3 grid gap-3">
                        <div className="rounded border border-slate-800 bg-slate-900 p-3">
                          <p className="text-[10px] font-bold uppercase text-slate-400">
                            Baseline 60 segundos
                          </p>
                          <p className="mt-2 text-xs text-slate-300">
                            IPM {fmt(report.baseline?.ipmAvg, 1)} | IDM {fmt(report.baseline?.idmAvg, 2)} |
                            Zona {report.baseline?.dominantZone || "--"} | Tom {report.baseline?.emotionalTone || "--"}
                          </p>
                        </div>
                        <div className="rounded border border-slate-800 bg-slate-900 p-3">
                          <p className="text-[10px] font-bold uppercase text-slate-400">
                            Cortes e resumos
                          </p>
                          <div className="mt-2 space-y-2">
                            {(report.conversationSummaries || []).map((cut) => (
                              <div key={cut.id} className="rounded border border-slate-800 bg-slate-950 p-2 text-xs">
                                <p className="font-black text-slate-100">
                                  {cut.startMinute}-{cut.endMinute}min | {cut.theme || "Tema não definido"}
                                </p>
                                <p className="mt-1 leading-5 text-slate-300">{cut.summary}</p>
                              </div>
                            ))}
                            {!report.conversationSummaries?.length && (
                              <p className="text-xs text-slate-400">Sem cortes resumidos nesta sessão.</p>
                            )}
                          </div>
                        </div>
                        <div className="rounded border border-slate-800 bg-slate-900 p-3">
                          <p className="text-[10px] font-bold uppercase text-slate-400">Dissonâncias</p>
                          {(report.dissonances || []).length ? (
                            <ul className="mt-2 space-y-2 text-xs text-slate-300">
                              {report.dissonances.map((item) => (
                                <li key={item.id} className="rounded border border-slate-800 bg-slate-950 p-2">
                                  {item.report}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-xs text-slate-400">
                              Nenhuma dissonância acima do limiar foi registrada.
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};
