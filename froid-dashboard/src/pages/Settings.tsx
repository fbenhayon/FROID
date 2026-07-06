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

type CalendarViewMode = "day" | "week" | "month";

type GoogleCalendarItem = {
  id: string;
  summary: string;
  primary?: boolean;
  accessRole?: string;
  backgroundColor?: string;
  selected?: boolean;
};

const dateInputValue = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const startOfLocalDay = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);

const addDays = (date: Date, days: number) => {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
};

const addMonths = (date: Date, months: number) => {
  const next = new Date(date);
  next.setMonth(next.getMonth() + months);
  return next;
};

const getWeekStart = (date: Date) => {
  const base = startOfLocalDay(date);
  const day = base.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(base, diff);
};

const getCalendarRange = (mode: CalendarViewMode, anchor: Date) => {
  if (mode === "day") {
    const start = startOfLocalDay(anchor);
    return { start, end: addDays(start, 1) };
  }
  if (mode === "week") {
    const start = getWeekStart(anchor);
    return { start, end: addDays(start, 7) };
  }
  const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 0, 0, 0, 0);
  const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1, 0, 0, 0, 0);
  return { start, end };
};

const getEventStart = (event: any) => {
  const value = event?.start?.dateTime || event?.start?.date;
  return value ? new Date(value) : null;
};

const getEventEnd = (event: any) => {
  const value = event?.end?.dateTime || event?.end?.date;
  return value ? new Date(value) : null;
};

const formatEventTime = (event: any) => {
  const start = getEventStart(event);
  const end = getEventEnd(event);
  if (!start) return "--";
  const startText = start.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const endText = end?.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return endText ? `${startText}-${endText}` : startText;
};

const formatRangeTitle = (mode: CalendarViewMode, anchor: Date) => {
  const { start, end } = getCalendarRange(mode, anchor);
  if (mode === "day") {
    return start.toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
    });
  }
  if (mode === "week") {
    return `${start.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
    })} - ${addDays(end, -1).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
    })}`;
  }
  return start.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
};

export const Settings: React.FC<SettingsProps> = ({ user }) => {
  const nav = useNavigate();
  const ownerEmail = useMemo(() => user?.email || "", [user?.email]);
  const [prompts, setPrompts] = useState<ProfessionalPrompt[]>([]);
  const [promptTitle, setPromptTitle] = useState("");
  const [promptText, setPromptText] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [calendarStatus, setCalendarStatus] = useState<any>(null);
  const [calendarItems, setCalendarItems] = useState<GoogleCalendarItem[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<any[]>([]);
  const [calendarMessage, setCalendarMessage] = useState("");
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarView, setCalendarView] = useState<CalendarViewMode>("week");
  const [calendarAnchor, setCalendarAnchor] = useState(() => startOfLocalDay(new Date()));
  const [eventTitle, setEventTitle] = useState("Sessao FROID");
  const [eventDate, setEventDate] = useState(() => dateInputValue(new Date()));
  const [eventStart, setEventStart] = useState("09:00");
  const [eventDuration, setEventDuration] = useState("50");

  const authHeaders = (): Record<string, string> => {
    const token = window.localStorage.getItem("froid_token") || "";
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadCalendarStatus = async (
    mode: CalendarViewMode = calendarView,
    anchor: Date = calendarAnchor,
  ) => {
    try {
      const response = await fetch(apiUrl("/api/google-calendar/status"), {
        headers: authHeaders(),
      });
      const data = response.ok ? await response.json() : null;
      setCalendarStatus(data);
      if (data?.connected) {
        const calendarsResponse = await fetch(apiUrl("/api/google-calendar/calendars"), {
          headers: authHeaders(),
        });
        const calendarsData = calendarsResponse.ok ? await calendarsResponse.json() : null;
        if (!calendarsResponse.ok) {
          setCalendarMessage(
            "Reconecte o Google para autorizar a selecao da agenda FROID dedicada.",
          );
        }
        const calendars = Array.isArray(calendarsData?.items) ? calendarsData.items : [];
        setCalendarItems(calendars);

        const { start, end } = getCalendarRange(mode, anchor);
        const eventsResponse = await fetch(
          apiUrl(
            `/api/google-calendar/events?max_results=100&time_min=${encodeURIComponent(
              start.toISOString(),
            )}&time_max=${encodeURIComponent(end.toISOString())}`,
          ),
          { headers: authHeaders() },
        );
        const eventsData = eventsResponse.ok ? await eventsResponse.json() : null;
        setCalendarEvents(Array.isArray(eventsData?.items) ? eventsData.items : []);
      } else {
        setCalendarItems([]);
        setCalendarEvents([]);
      }
    } catch {
      setCalendarStatus({ connected: false, configured: false });
      setCalendarItems([]);
      setCalendarEvents([]);
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

  const reloadCalendarRange = async (
    mode: CalendarViewMode = calendarView,
    anchor: Date = calendarAnchor,
  ) => {
    setCalendarLoading(true);
    try {
      await loadCalendarStatus(mode, anchor);
    } finally {
      setCalendarLoading(false);
    }
  };

  const selectCalendar = async (calendarId: string) => {
    const calendar = calendarItems.find((item) => item.id === calendarId);
    setCalendarLoading(true);
    setCalendarMessage("");
    try {
      const response = await fetch(apiUrl("/api/google-calendar/select-calendar"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({
          calendar_id: calendarId,
          calendar_summary: calendar?.summary || calendarId,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Nao foi possivel selecionar a agenda.");
      setCalendarStatus((current: any) => ({ ...(current || {}), ...data }));
      setCalendarMessage(`Agenda ativa: ${calendar?.summary || calendarId}`);
      await loadCalendarStatus(calendarView, calendarAnchor);
    } catch (error: any) {
      setCalendarMessage(error?.message || "Falha ao selecionar agenda.");
    } finally {
      setCalendarLoading(false);
    }
  };

  const changeCalendarView = async (mode: CalendarViewMode) => {
    setCalendarView(mode);
    await reloadCalendarRange(mode, calendarAnchor);
  };

  const moveCalendar = async (direction: -1 | 1) => {
    const next =
      calendarView === "month"
        ? addMonths(calendarAnchor, direction)
        : addDays(calendarAnchor, direction * (calendarView === "week" ? 7 : 1));
    setCalendarAnchor(next);
    await reloadCalendarRange(calendarView, next);
  };

  const createCalendarEvent = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!eventTitle.trim() || !eventDate || !eventStart) return;
    setCalendarLoading(true);
    setCalendarMessage("");
    try {
      const start = new Date(`${eventDate}T${eventStart}:00`);
      const end = new Date(start);
      end.setMinutes(end.getMinutes() + Math.max(15, Number(eventDuration) || 50));
      const response = await fetch(apiUrl("/api/google-calendar/events"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({
          summary: eventTitle.trim(),
          start: start.toISOString(),
          end: end.toISOString(),
          timeZone: "America/Sao_Paulo",
          description: "Evento criado pelo FROID para organizacao da sessao clinica.",
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Nao foi possivel criar o evento.");
      setCalendarMessage("Evento criado na agenda selecionada.");
      await loadCalendarStatus(calendarView, calendarAnchor);
    } catch (error: any) {
      setCalendarMessage(error?.message || "Falha ao criar evento na agenda.");
    } finally {
      setCalendarLoading(false);
    }
  };

  const deleteCalendarEvent = async (eventId: string) => {
    if (!eventId) return;
    setCalendarLoading(true);
    setCalendarMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/google-calendar/events/${encodeURIComponent(eventId)}`),
        {
          method: "DELETE",
          headers: authHeaders(),
        },
      );
      const data = response.status === 204 ? {} : await response.json();
      if (!response.ok) throw new Error(data?.detail || "Nao foi possivel excluir o evento.");
      setCalendarMessage("Evento removido da agenda.");
      await loadCalendarStatus(calendarView, calendarAnchor);
    } catch (error: any) {
      setCalendarMessage(error?.message || "Falha ao remover evento.");
    } finally {
      setCalendarLoading(false);
    }
  };

  const calendarDays = useMemo(() => {
    const { start, end } = getCalendarRange(calendarView, calendarAnchor);
    const days: Date[] = [];
    for (let day = new Date(start); day < end; day = addDays(day, 1)) {
      days.push(day);
    }
    return days;
  }, [calendarView, calendarAnchor]);

  const eventsByDay = useMemo(() => {
    const groups: Record<string, any[]> = {};
    calendarDays.forEach((day) => {
      groups[dateInputValue(day)] = [];
    });
    calendarEvents.forEach((event) => {
      const start = getEventStart(event);
      if (!start) return;
      const key = dateInputValue(start);
      if (!groups[key]) groups[key] = [];
      groups[key].push(event);
    });
    Object.values(groups).forEach((items) =>
      items.sort((a, b) => {
        const aStart = getEventStart(a)?.getTime() || 0;
        const bStart = getEventStart(b)?.getTime() || 0;
        return aStart - bStart;
      }),
    );
    return groups;
  }, [calendarDays, calendarEvents]);

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
          <div className="rounded-lg border border-slate-700 p-3 md:col-span-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">Google OAuth e Agenda</p>
                <p className="mt-1 text-xs text-slate-400">
                  Conecte, selecione e altere a agenda do profissional para organizar sessoes FROID.
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
              <div className="mt-3 grid gap-3 rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300 lg:grid-cols-[1fr_1.2fr]">
                <div>
                  <p>
                    <strong>Conta:</strong>{" "}
                    {calendarStatus.google_email || calendarStatus.professional_email || ownerEmail}
                  </p>
                  <p className="mt-1">
                    <strong>Agenda ativa:</strong>{" "}
                    {calendarStatus.selected_calendar_summary || "Agenda principal"}
                  </p>
                  <p className="mt-1">
                    <strong>Atualizado:</strong>{" "}
                    {calendarStatus.updated_at
                      ? new Date(calendarStatus.updated_at).toLocaleString("pt-BR")
                      : "--"}
                  </p>
                </div>
                <div className="rounded border border-cyan-900/70 bg-cyan-950/30 p-2 text-cyan-100">
                  Recomendacao FROID: crie no Google Calendar uma agenda separada chamada{" "}
                  <strong>FROID - Sessoes</strong> e selecione essa agenda aqui. Isso preserva a
                  organizacao clinica, facilita auditoria e evita misturar agenda pessoal com agenda
                  terapeutica.
                </div>
              </div>
            )}
            {calendarStatus?.connected && (
              <div className="mt-3 space-y-3">
                <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
                  <label className="text-xs text-slate-300">
                    <span className="font-black uppercase tracking-wide text-cyan-200">
                      Agenda Google para sessoes
                    </span>
                    <select
                      value={calendarStatus.selected_calendar_id || "primary"}
                      onChange={(event) => void selectCalendar(event.target.value)}
                      disabled={calendarLoading || calendarItems.length === 0}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500"
                    >
                      {calendarItems.length === 0 && <option value="primary">Agenda principal</option>}
                      {calendarItems.map((calendar) => (
                        <option key={calendar.id} value={calendar.id}>
                          {calendar.summary}
                          {calendar.primary ? " (principal)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="flex items-end gap-2">
                    {(["day", "week", "month"] as CalendarViewMode[]).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => void changeCalendarView(mode)}
                        className={`rounded-lg px-3 py-2 text-xs font-black uppercase ${
                          calendarView === mode
                            ? "bg-cyan-700 text-white"
                            : "border border-slate-700 bg-slate-950 text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        {mode === "day" ? "Diario" : mode === "week" ? "Semanal" : "Mensal"}
                      </button>
                    ))}
                  </div>
                </div>

                <form
                  onSubmit={createCalendarEvent}
                  className="grid gap-2 rounded border border-slate-700 bg-slate-950 p-3 lg:grid-cols-[1.4fr_0.8fr_0.6fr_0.6fr_auto]"
                >
                  <label className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    Titulo
                    <input
                      value={eventTitle}
                      onChange={(event) => setEventTitle(event.target.value)}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-xs font-semibold normal-case tracking-normal text-slate-100 outline-none focus:border-cyan-500"
                    />
                  </label>
                  <label className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    Data
                    <input
                      type="date"
                      value={eventDate}
                      onChange={(event) => setEventDate(event.target.value)}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-xs font-semibold normal-case tracking-normal text-slate-100 outline-none focus:border-cyan-500"
                    />
                  </label>
                  <label className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    Inicio
                    <input
                      type="time"
                      value={eventStart}
                      onChange={(event) => setEventStart(event.target.value)}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-xs font-semibold normal-case tracking-normal text-slate-100 outline-none focus:border-cyan-500"
                    />
                  </label>
                  <label className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    Min
                    <input
                      type="number"
                      min="15"
                      step="5"
                      value={eventDuration}
                      onChange={(event) => setEventDuration(event.target.value)}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-xs font-semibold normal-case tracking-normal text-slate-100 outline-none focus:border-cyan-500"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={calendarLoading}
                    className="self-end rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
                  >
                    Criar evento
                  </button>
                </form>

                <div className="rounded border border-slate-700 bg-slate-950 p-3">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-wide text-cyan-200">
                        Agenda FROID
                      </p>
                      <p className="text-sm font-bold capitalize text-slate-100">
                        {formatRangeTitle(calendarView, calendarAnchor)}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void moveCalendar(-1)}
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-bold text-slate-200 hover:bg-slate-800"
                      >
                        Anterior
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const today = startOfLocalDay(new Date());
                          setCalendarAnchor(today);
                          void reloadCalendarRange(calendarView, today);
                        }}
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-bold text-slate-200 hover:bg-slate-800"
                      >
                        Hoje
                      </button>
                      <button
                        type="button"
                        onClick={() => void moveCalendar(1)}
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-bold text-slate-200 hover:bg-slate-800"
                      >
                        Proximo
                      </button>
                    </div>
                  </div>

                  <div
                    className={`grid gap-2 ${
                      calendarView === "day"
                        ? "grid-cols-1"
                        : calendarView === "week"
                          ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-7"
                          : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7"
                    }`}
                  >
                    {calendarDays.map((day) => {
                      const key = dateInputValue(day);
                      const dayEvents = eventsByDay[key] || [];
                      return (
                        <div
                          key={key}
                          className="min-h-[128px] rounded border border-slate-800 bg-slate-900/80 p-2"
                        >
                          <div className="mb-2 border-b border-slate-800 pb-1">
                            <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
                              {day.toLocaleDateString("pt-BR", { weekday: "short" })}
                            </p>
                            <p className="text-xs font-bold text-slate-100">
                              {day.toLocaleDateString("pt-BR", {
                                day: "2-digit",
                                month: "2-digit",
                              })}
                            </p>
                          </div>
                          {dayEvents.length === 0 ? (
                            <p className="text-[10px] italic text-slate-600">Sem eventos</p>
                          ) : (
                            <div className="space-y-1.5">
                              {dayEvents.map((event) => (
                                <div
                                  key={event.id}
                                  className="rounded border border-cyan-900/80 bg-cyan-950/30 p-2 text-xs"
                                >
                                  <p className="font-black text-cyan-100">{formatEventTime(event)}</p>
                                  <p className="mt-0.5 line-clamp-2 font-semibold text-slate-100">
                                    {event.summary}
                                  </p>
                                  <div className="mt-1 flex flex-wrap gap-2">
                                    {event.htmlLink && (
                                      <a
                                        href={event.htmlLink}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-[10px] font-bold text-cyan-200 underline"
                                      >
                                        Abrir
                                      </a>
                                    )}
                                    <button
                                      type="button"
                                      onClick={() => void deleteCalendarEvent(event.id)}
                                      className="text-[10px] font-bold text-red-200 underline"
                                    >
                                      Remover
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
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
          <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 p-3">
            <p className="text-sm font-semibold">Consentimentos LGPD</p>
            <span className="text-xs font-bold text-slate-400">
              Duvidas e referencias pelo FROID Explica
            </span>
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


