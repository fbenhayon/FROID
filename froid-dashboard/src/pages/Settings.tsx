import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import {
  createProfessionalPrompt,
  loadProfessionalPrompts,
  saveProfessionalPrompts,
  type ProfessionalPrompt,
} from "../lib/professional-prompts";

interface SettingsProps {
  user?: FroidUser | null;
}

export const Settings: React.FC<SettingsProps> = ({ user }) => {
  const nav = useNavigate();
  const ownerEmail = useMemo(() => user?.email || "", [user?.email]);
  const [prompts, setPrompts] = useState<ProfessionalPrompt[]>([]);
  const [promptTitle, setPromptTitle] = useState("");
  const [promptText, setPromptText] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [calendarStatus, setCalendarStatus] = useState<any>(null);
  const [calendarEvents, setCalendarEvents] = useState<any[]>([]);
  const [calendarMessage, setCalendarMessage] = useState("");
  const [calendarLoading, setCalendarLoading] = useState(false);

  const authHeaders = (): Record<string, string> => {
    const token = window.localStorage.getItem("froid_token") || "";
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadCalendarStatus = async () => {
    try {
      const response = await fetch(apiUrl("/api/google-calendar/status"), {
        headers: authHeaders(),
      });
      const data = response.ok ? await response.json() : null;
      setCalendarStatus(data);
      if (data?.connected) {
        const eventsResponse = await fetch(apiUrl("/api/google-calendar/events?max_results=5"), {
          headers: authHeaders(),
        });
        const eventsData = eventsResponse.ok ? await eventsResponse.json() : null;
        setCalendarEvents(Array.isArray(eventsData?.items) ? eventsData.items : []);
      } else {
        setCalendarEvents([]);
      }
    } catch {
      setCalendarStatus({ connected: false, configured: false });
    }
  };

  useEffect(() => {
    setPrompts(loadProfessionalPrompts(ownerEmail));
  }, [ownerEmail]);

  useEffect(() => {
    void loadCalendarStatus();
  }, []);

  const addPrompt = (event: React.FormEvent) => {
    event.preventDefault();
    const title = promptTitle.trim();
    const text = promptText.trim();
    if (!title || !text) return;

    const next = [createProfessionalPrompt(title, text), ...prompts].slice(0, 40);
    setPrompts(next);
    saveProfessionalPrompts(ownerEmail, next);
    setPromptTitle("");
    setPromptText("");
    setSavedMessage("Prompt do profissional salvo.");
    window.setTimeout(() => setSavedMessage(""), 2500);
  };

  const removePrompt = (promptId: string) => {
    const next = prompts.filter((prompt) => prompt.id !== promptId);
    setPrompts(next);
    saveProfessionalPrompts(ownerEmail, next);
    setSavedMessage("Prompt removido.");
    window.setTimeout(() => setSavedMessage(""), 2500);
  };

  const connectGoogleCalendar = async () => {
    setCalendarLoading(true);
    setCalendarMessage("");
    try {
      const response = await fetch(apiUrl("/api/google-calendar/connect"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({ base_url: apiUrl("").replace(/\/+$/, "") }),
      });
      const data = await response.json();
      if (!response.ok || !data?.auth_url) {
        throw new Error(data?.detail || "Nao foi possivel iniciar a conexao Google Agenda.");
      }
      window.location.href = data.auth_url;
    } catch (error: any) {
      setCalendarMessage(error?.message || "Falha ao conectar Google Agenda.");
      setCalendarLoading(false);
    }
  };

  const disconnectGoogleCalendar = async () => {
    setCalendarLoading(true);
    setCalendarMessage("");
    try {
      const response = await fetch(apiUrl("/api/google-calendar/disconnect"), {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error("Nao foi possivel desconectar Google Agenda.");
      setCalendarMessage("Google Agenda desconectado.");
      await loadCalendarStatus();
    } catch (error: any) {
      setCalendarMessage(error?.message || "Falha ao desconectar Google Agenda.");
    } finally {
      setCalendarLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-5xl space-y-6 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">Configuracoes do Profissional</h1>
            <p className="mt-1 text-sm text-slate-400">
              Gestao clinica, consentimentos, agenda, auditoria e prompts proprios do FROID Explica.
            </p>
          </div>
          {ownerEmail && (
            <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-slate-300">
              {ownerEmail}
            </span>
          )}
        </div>

        <section className="rounded-xl border border-cyan-800 bg-cyan-950/50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-cyan-100">Prompts proprios do profissional</p>
              <p className="mt-1 text-xs leading-5 text-cyan-200">
                Estes prompts aparecem separados dos prompts nativos no dropdown do FROID Explica.
                Eles ficam vinculados ao e-mail do profissional neste navegador.
              </p>
            </div>
            <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-bold text-cyan-200">
              {prompts.length} personalizados
            </span>
          </div>

          <form onSubmit={addPrompt} className="mt-4 grid gap-3">
            <label>
              <span className="text-xs font-bold uppercase tracking-wide text-cyan-100">
                Titulo curto
              </span>
              <input
                value={promptTitle}
                onChange={(event) => setPromptTitle(event.target.value)}
                placeholder="Ex: Risco familiar recente"
                className="mt-1 w-full rounded-lg border border-cyan-200 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                maxLength={90}
              />
            </label>
            <label>
              <span className="text-xs font-bold uppercase tracking-wide text-cyan-100">
                Prompt completo
              </span>
              <textarea
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                placeholder="Escreva a pergunta ou comando que deseja reutilizar no FROID Explica..."
                rows={4}
                className="mt-1 w-full rounded-lg border border-cyan-200 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <button
                disabled={!promptTitle.trim() || !promptText.trim()}
                className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
              >
                Salvar prompt
              </button>
              {savedMessage && <span className="text-xs font-bold text-cyan-200">{savedMessage}</span>}
            </div>
          </form>

          {prompts.length > 0 && (
            <div className="mt-4 divide-y divide-slate-800 rounded-lg border border-cyan-800 bg-slate-950">
              {prompts.map((prompt) => (
                <div key={prompt.id} className="grid gap-2 p-3 md:grid-cols-[1fr_auto]">
                  <div>
                    <p className="text-sm font-bold text-slate-100">{prompt.title}</p>
                    <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-300">
                      {prompt.text}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removePrompt(prompt.id)}
                    className="h-fit rounded-lg border border-red-800 px-3 py-1.5 text-xs font-bold text-red-200 hover:bg-red-950/40"
                  >
                    Excluir
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-700 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">Google OAuth e Agenda</p>
                <p className="mt-1 text-xs text-slate-400">
                  Conecte a agenda do profissional para consultar compromissos e preparar lembretes de sessoes.
                </p>
              </div>
              <span
                className={`rounded px-2 py-1 text-[10px] font-black uppercase ${
                  calendarStatus?.connected
                    ? "border border-emerald-700 bg-emerald-950/40 text-emerald-200"
                    : "border border-amber-600 bg-amber-950/40 text-amber-100"
                }`}
              >
                {calendarStatus?.connected ? "Conectado" : "Pendente"}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              URI de retorno:{" "}
              <span className="font-mono text-[10px] text-cyan-200">
                {calendarStatus?.redirect_uri || "aguardando servidor"}
              </span>
            </p>
            {calendarStatus?.connected && (
              <div className="mt-3 rounded border border-slate-700 bg-slate-950 p-2 text-xs text-slate-300">
                <p>
                  <strong>Conta:</strong>{" "}
                  {calendarStatus.google_email || calendarStatus.professional_email || ownerEmail}
                </p>
                <p className="mt-1">
                  <strong>Atualizado:</strong>{" "}
                  {calendarStatus.updated_at
                    ? new Date(calendarStatus.updated_at).toLocaleString("pt-BR")
                    : "--"}
                </p>
              </div>
            )}
            {calendarEvents.length > 0 && (
              <div className="mt-3 space-y-1 rounded border border-slate-700 bg-slate-950 p-2">
                <p className="text-[10px] font-black uppercase tracking-wide text-cyan-200">
                  Proximos eventos
                </p>
                {calendarEvents.map((event) => (
                  <div key={event.id} className="border-t border-slate-800 pt-1 text-xs text-slate-300">
                    <p className="font-bold text-slate-100">{event.summary}</p>
                    <p className="text-[10px] text-slate-500">
                      {event.start?.dateTime || event.start?.date || "--"}
                    </p>
                  </div>
                ))}
              </div>
            )}
            {calendarMessage && (
              <p className="mt-3 rounded border border-amber-600 bg-amber-950/40 px-2 py-1 text-xs font-bold text-amber-100">
                {calendarMessage}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={calendarLoading}
                onClick={connectGoogleCalendar}
                className="rounded-lg bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
              >
                {calendarStatus?.connected ? "Reconectar Google" : "Conectar Google"}
              </button>
              {calendarStatus?.connected && (
                <button
                  type="button"
                  disabled={calendarLoading}
                  onClick={disconnectGoogleCalendar}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-bold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
                >
                  Desconectar
                </button>
              )}
            </div>
          </div>
          <div className="rounded-lg border border-slate-700 p-3">
            <p className="text-sm font-semibold">Consentimentos LGPD</p>
            <p className="mt-1 text-xs text-slate-400">
              Aceite granular com quarentena e exclusao sob aprovacao do DPO.
            </p>
            <div className="mt-3 text-xs text-slate-300">
              Pesquisa anonima ativada - Compartilhamento com terceiros desativado
            </div>
          </div>
          <div className="rounded-lg border border-slate-700 p-3">
            <p className="text-sm font-semibold">Planos e Cobranca</p>
            <p className="mt-1 text-xs text-slate-400">
              Checkout Stripe e controle de creditos de sessao FROID.
            </p>
            <div className="mt-3 flex gap-2 text-xs">
              <span className="rounded-full bg-blue-950 px-2 py-0.5 text-blue-200">
                Sessao avulsa
              </span>
              <span className="rounded-full bg-emerald-950/40 px-2 py-0.5 text-emerald-200">
                Pacote 25
              </span>
            </div>
          </div>
          <div className="rounded-lg border border-slate-700 p-3">
            <p className="text-sm font-semibold">Auditoria e Ledger</p>
            <p className="mt-1 text-xs text-slate-400">
              Hash chain local para consentimentos, exclusao e acesso as sessoes.
            </p>
            <div className="mt-3 text-xs text-slate-300">
              SHA256 - 90 dias de purga - DPO-admin
            </div>
          </div>
        </div>

        <button
          onClick={() => nav("/dashboard")}
          className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
};


