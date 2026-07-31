import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../lib/api";
import { dashboardText, loadSessionLanguagePreferences } from "../lib/localization";
import { rememberSessionPatient } from "../lib/session-report";

interface WaitingSession {
  session_id: string;
  patient_id?: string;
  patient_name?: string;
  patient_email?: string;
  patient_phone?: string;
  session_mode?: "remote" | "presential" | "presential_mobile";
  joined_at?: string;
  patient_connected?: boolean;
}

function joinedTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function WaitingPatientSessions() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<WaitingSession[]>([]);
  const locale = loadSessionLanguagePreferences().spokenLanguage;
  const tr = (text: string) => dashboardText(locale, text);
  // Sessões já direcionadas automaticamente — evita redirecionar de novo o
  // mesmo paciente (ex.: se o profissional voltar ao dashboard depois).
  const redirectedIdsRef = useRef<Set<string>>(new Set());
  const autoRedirectTimerRef = useRef<number | null>(null);

  const openSession = useCallback(
    (session: WaitingSession) => {
      rememberSessionPatient(session.session_id, {
        id: session.patient_id,
        name: session.patient_name || "Paciente",
        email: session.patient_email,
        phone: session.patient_phone,
        sessionMode: session.session_mode || "remote",
        captureProfile:
          session.session_mode === "presential_mobile"
            ? "patient_mobile"
            : "patient_external_media",
      });
      navigate(`/session/${session.session_id}`);
    },
    [navigate],
  );

  const refresh = useCallback(async () => {
    const token = localStorage.getItem("froid_token") || "";
    if (!token) {
      setSessions([]);
      return;
    }
    try {
      const response = await fetch(apiUrl("/api/session-waiting"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const payload = await response.json();
      const nextSessions: WaitingSession[] = Array.isArray(payload?.waiting)
        ? payload.waiting
        : [];
      setSessions(nextSessions);
      // O paciente já está conectado na sala (patient_connected) quando esta
      // lista o inclui — direciona automaticamente o profissional para a
      // sessão, sem exigir clique manual em "Atender".
      const toRedirect = nextSessions.find(
        (session) => !redirectedIdsRef.current.has(session.session_id),
      );
      if (toRedirect && autoRedirectTimerRef.current === null) {
        redirectedIdsRef.current.add(toRedirect.session_id);
        autoRedirectTimerRef.current = window.setTimeout(() => {
          autoRedirectTimerRef.current = null;
          openSession(toRedirect);
        }, 800);
      }
    } catch {
      // A sinalização pode se reconectar; a próxima consulta atualiza o estado.
    }
  }, [openSession]);

  useEffect(() => {
    void refresh();
    const intervalId = window.setInterval(refresh, 2500);
    const handleFocus = () => void refresh();
    window.addEventListener("focus", handleFocus);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      if (autoRedirectTimerRef.current !== null) {
        window.clearTimeout(autoRedirectTimerRef.current);
        autoRedirectTimerRef.current = null;
      }
    };
  }, [refresh]);

  if (!sessions.length) return null;

  return (
    <section
      className="rounded-lg border border-emerald-600 bg-emerald-950 p-3 shadow-lg shadow-emerald-950/30"
      aria-live="assertive"
      aria-label="Pacientes aguardando atendimento"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-black text-white">
            {sessions.length === 1
              ? tr("Paciente aguardando atendimento")
              : `${sessions.length} ${tr("Pacientes aguardando atendimento")}`}
          </h2>
          <p className="mt-0.5 text-xs text-emerald-100">
            {tr("Você será direcionado automaticamente. Use os botões para escolher outro paciente ou entrar antes do redirecionamento.")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {sessions.map((session) => (
            <button
              key={session.session_id}
              type="button"
              onClick={() => openSession(session)}
              className="rounded-lg border border-blue-300 bg-blue-700 px-4 py-2 text-xs font-black text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-white"
            >
              {tr("Atender")} {session.patient_name || tr("Paciente")}
              {joinedTime(session.joined_at)
                ? ` · ${tr("desde")} ${joinedTime(session.joined_at)}`
                : ""}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
