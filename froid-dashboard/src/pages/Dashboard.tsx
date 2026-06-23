import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  fmtDelta,
  formatDateTime,
  limitWords,
  mergeReports,
  reportEndDate,
  shortId,
} from "../lib/patient-dashboard";
import {
  loadSessionReports,
  rememberSessionPatient,
  SessionReportRecord,
} from "../lib/session-report";

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
  patient_id?: string;
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

interface SessionEvent {
  id: number;
  type: "invite_created" | "invite_opened" | "invite_accepted" | "patient_joined";
  session_id: string;
  patient_name?: string;
  created_at: string;
}

function makeId() {
  return `froid-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
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
  const [patientActivity, setPatientActivity] = useState("");
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const professionalName = user?.name || user?.email || "Profissional";

  useEffect(() => {
    setReports(loadSessionReports());
    let active = true;
    fetch(apiUrl("/api/session-reports"))
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active) return;
        const remoteReports: SessionReportRecord[] = Array.isArray(data?.reports)
          ? data.reports
          : Array.isArray(data)
            ? data
            : [];
        if (remoteReports.length) {
          setReports((current) => mergeReports(current, remoteReports));
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const patientGroups = useMemo(() => buildPatientGroups(reports), [reports]);
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
        throw new Error(data?.detail || "Nao foi possivel criar o convite.");
      }
      setInviteResult(data);
      rememberSessionPatient(data.session_id, {
        id: data.patient_id,
        name: form.patient_name,
        email: form.patient_email,
        phone: form.patient_phone,
      });
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Falha ao criar convite.");
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

  useEffect(() => {
    let active = true;

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
        const visibleEvents = events.filter((event) =>
          ["invite_opened", "invite_accepted", "patient_joined"].includes(
            event.type,
          ),
        );
        const latest = visibleEvents[visibleEvents.length - 1];
        if (!latest || !active) return;
        const patient = latest.patient_name || "Paciente";
        if (latest.type === "invite_opened") {
          setPatientActivity(`${patient} abriu o convite FROID.`);
        }
        if (latest.type === "invite_accepted") {
          setPatientActivity(`${patient} confirmou cadastro e consentimentos LGPD.`);
        }
        if (
          latest.type === "patient_joined" &&
          latest.session_id &&
          !redirectingRef.current
        ) {
          setPatientActivity(`${patient} entrou na sessao. Abrindo sala profissional...`);
          rememberSessionPatient(latest.session_id, { name: patient });
          redirectingRef.current = true;
          window.setTimeout(() => {
            if (active) nav(`/session/${latest.session_id}`);
          }, 900);
        }
      } catch {
        // Polling best-effort.
      }
    };

    void pollSessionEvents();
    const intervalId = window.setInterval(pollSessionEvents, 3000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [nav]);

  return (
    <div className="min-h-screen bg-white p-1 text-black">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">FROID Dashboard</h1>
          <p className="mt-4 text-xs">Bem-vindo, {professionalName}</p>
        </div>
        <button className="border border-black px-2 py-0.5 text-[10px]">
          Sair
        </button>
      </div>

      {patientActivity && (
        <p className="mt-3 border border-cyan-600 bg-cyan-50 px-2 py-1 text-xs font-bold text-cyan-900">
          {patientActivity}
        </p>
      )}

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-base font-bold">Meus Pacientes</h2>
        <button
          onClick={() => nav(`/session/${makeId()}`)}
          className="border border-black px-2 py-0.5 text-[10px]"
        >
          + Nova Sessao Direta
        </button>
      </div>

      <section className="mt-3 border-t border-black">
        {patientGroups.length === 0 && (
          <div className="border-b border-black py-4 text-xs">
            Nenhum paciente com relatorio encontrado. Finalize uma sessao para
            alimentar o dashboard profissional.
          </div>
        )}

        {patientGroups.map((group) => (
          <article key={group.key} className="border-b-2 border-black py-3">
            <div className="flex justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold">
                  {group.patient.name || "Paciente sem nome"}
                </h3>
                <p className="mt-3 text-xs">
                  CPF: {group.patient.document || "Nao informado"}
                </p>
              </div>
              <button
                onClick={() => nav(`/patients/${encodeURIComponent(group.key)}`)}
                className="h-fit border border-black px-2 py-0.5 text-[10px]"
              >
                Ver Detalhes
              </button>
            </div>

            <div className="mt-6">
              <p className="text-xs font-bold">Ultimas 3 Sessoes</p>
              <div className="mt-4 space-y-1">
                {group.reports.slice(0, 3).map((report, index) => (
                  <div
                    key={report.sessionId}
                    className="grid grid-cols-[1fr_auto] gap-3 text-xs"
                  >
                    <button
                      onClick={() => nav(`/session/${report.sessionId}/report`)}
                      className="text-left underline-offset-2 hover:underline"
                    >
                      {index === 0 ? "Concluida " : "Ativa "}
                      {formatDateTime(reportEndDate(report))}
                    </button>
                    <span>ID: {shortId(report.sessionId)}</span>
                    <div className="col-span-2 text-[11px] text-slate-700">
                      Linha comparativa: IPM {fmt(report.baseline.ipmAvg, 1)} -&gt;{" "}
                      {fmt(report.sessionAverage.ipmAvg, 1)} (
                      {fmtDelta(
                        report.sessionAverage.ipmAvg - report.baseline.ipmAvg,
                        1,
                      )}
                      ) | IDM {fmt(report.baseline.idmAvg, 2)} -&gt;{" "}
                      {fmt(report.sessionAverage.idmAvg, 2)} | Zona{" "}
                      {report.sessionAverage.dominantZone || "--"} | Tema{" "}
                      {limitWords(
                        report.sessionAverage.theme || report.baseline.theme,
                        4,
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </article>
        ))}
      </section>

      <section className="mt-6 border border-black p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold">Convite de sessao ao paciente</h2>
          <span className="text-[10px] font-bold uppercase">Algoritmo inicial</span>
        </div>
        <form onSubmit={createInvite} className="grid gap-2 md:grid-cols-4">
          <label className="text-xs font-bold">
            Nome do paciente
            <input
              value={form.patient_name}
              onChange={(event) => updateForm("patient_name", event.target.value)}
              className="mt-1 w-full border border-black px-2 py-1 font-normal"
            />
          </label>
          <label className="text-xs font-bold">
            WhatsApp
            <input
              value={form.patient_phone}
              onChange={(event) => updateForm("patient_phone", event.target.value)}
              className="mt-1 w-full border border-black px-2 py-1 font-normal"
            />
          </label>
          <label className="text-xs font-bold">
            E-mail
            <input
              value={form.patient_email}
              onChange={(event) => updateForm("patient_email", event.target.value)}
              className="mt-1 w-full border border-black px-2 py-1 font-normal"
            />
          </label>
          <label className="text-xs font-bold">
            Forma de pagamento
            <select
              value={form.payment_mode}
              onChange={(event) =>
                updateForm("payment_mode", event.target.value as PaymentMode)
              }
              className="mt-1 w-full border border-black px-2 py-1 font-normal"
            >
              <option value="single">Sessao avulsa com PIX</option>
              <option value="package">Pacote de sessoes</option>
            </select>
          </label>
          <label className="text-xs font-bold">
            Valor da sessao (R$)
            <input
              value={form.session_value}
              onChange={(event) => updateForm("session_value", event.target.value)}
              className="mt-1 w-full border border-black px-2 py-1 font-normal"
            />
          </label>
          {form.payment_mode === "package" ? (
            <label className="text-xs font-bold">
              Numero de sessoes
              <input
                type="number"
                min={1}
                value={form.package_sessions}
                onChange={(event) =>
                  updateForm("package_sessions", event.target.value)
                }
                className="mt-1 w-full border border-black px-2 py-1 font-normal"
              />
            </label>
          ) : (
            <label className="text-xs font-bold md:col-span-2">
              Codigo PIX copia e cola
              <input
                value={form.pix_code}
                onChange={(event) => updateForm("pix_code", event.target.value)}
                className="mt-1 w-full border border-black px-2 py-1 font-normal"
              />
            </label>
          )}
          <div className="self-end">
            <button
              type="submit"
              disabled={creatingInvite}
              className="w-full border border-black bg-black px-3 py-1 font-bold text-white disabled:opacity-50"
            >
              {creatingInvite ? "Gerando..." : "Gerar convite"}
            </button>
            {inviteError && (
              <p className="mt-1 text-xs font-bold text-red-600">{inviteError}</p>
            )}
          </div>
        </form>

        {inviteResult && (
          <div className="mt-3 border border-black p-2 text-xs">
            <p className="font-bold">
              Convite criado: {inviteResult.session_id} |{" "}
              {inviteResult.patient_known ? "paciente cadastrado" : "novo cadastro"}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                onClick={() => copyText(inviteResult.whatsapp_message)}
                className="border border-black px-2 py-1"
              >
                Copiar mensagem
              </button>
              <button
                onClick={() => copyText(inviteResult.invite_url)}
                className="border border-black px-2 py-1"
              >
                Copiar link
              </button>
              <button
                onClick={() => nav(`/session/${inviteResult.session_id}`)}
                className="border border-black px-2 py-1"
              >
                Abrir sala profissional
              </button>
            </div>
            <textarea
              readOnly
              value={inviteResult.whatsapp_message}
              className="mt-2 h-28 w-full border border-black p-2"
            />
          </div>
        )}
      </section>
    </div>
  );
};
