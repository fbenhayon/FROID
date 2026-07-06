import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiUrl } from "../../lib/api";

interface AgendaReminder {
  id: string;
  summary: string;
  startsAt: string;
  minutesUntil: number;
}

function calendarEventStartMs(event: any) {
  const raw = event?.start?.dateTime || event?.start?.date;
  if (!raw) return null;
  const timestamp = new Date(raw).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

function isClinicalPath(pathname: string) {
  return [
    "/dashboard",
    "/session/",
    "/patients/",
    "/history",
    "/settings",
  ].some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

export const AgendaReminderBanner: React.FC<{ enabled: boolean }> = ({ enabled }) => {
  const location = useLocation();
  const [agendaReminder, setAgendaReminder] = useState<AgendaReminder | null>(null);
  const shouldRun = enabled && isClinicalPath(location.pathname);

  useEffect(() => {
    if (!shouldRun) {
      setAgendaReminder(null);
      return;
    }

    let active = true;

    const loadAgendaReminder = async () => {
      try {
        const token = localStorage.getItem("froid_token") || "";
        if (!token) {
          if (active) setAgendaReminder(null);
          return;
        }
        const headers = { Authorization: `Bearer ${token}` };
        const statusResponse = await fetch(apiUrl("/api/google-calendar/status"), {
          headers,
        });
        const status = statusResponse.ok ? await statusResponse.json() : null;
        if (!status?.connected) {
          if (active) setAgendaReminder(null);
          return;
        }

        const now = new Date();
        const reminderWindowEnd = new Date(now.getTime() + 5 * 60 * 1000);
        const eventsResponse = await fetch(
          apiUrl(
            `/api/google-calendar/events?max_results=10&time_min=${encodeURIComponent(
              now.toISOString(),
            )}&time_max=${encodeURIComponent(reminderWindowEnd.toISOString())}`,
          ),
          { headers },
        );
        const data = eventsResponse.ok ? await eventsResponse.json() : null;
        const nextEvent = (Array.isArray(data?.items) ? data.items : [])
          .map((event: any) => ({
            event,
            startMs: calendarEventStartMs(event),
          }))
          .filter(
            (item: { event: any; startMs: number | null }): item is { event: any; startMs: number } =>
              typeof item.startMs === "number" &&
              item.startMs >= now.getTime() - 30 * 1000 &&
              item.startMs <= reminderWindowEnd.getTime(),
          )
          .sort((a: { startMs: number }, b: { startMs: number }) => a.startMs - b.startMs)[0];

        if (!active) return;
        if (!nextEvent) {
          setAgendaReminder(null);
          return;
        }
        setAgendaReminder({
          id: String(nextEvent.event.id || nextEvent.startMs),
          summary: String(nextEvent.event.summary || "Consulta FROID"),
          startsAt: new Date(nextEvent.startMs).toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit",
          }),
          minutesUntil: Math.max(0, Math.ceil((nextEvent.startMs - now.getTime()) / 60000)),
        });
      } catch {
        if (active) setAgendaReminder(null);
      }
    };

    void loadAgendaReminder();
    const intervalId = window.setInterval(loadAgendaReminder, 60000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [shouldRun]);

  if (!agendaReminder) return null;

  return (
    <div className="pointer-events-none fixed left-0 right-0 top-3 z-50 flex justify-center px-4">
      <div className="pointer-events-auto rounded-lg border border-amber-500/60 bg-slate-950/95 px-4 py-2 text-xs font-bold text-amber-100 shadow-2xl shadow-slate-950/50 backdrop-blur">
        Consulta em {agendaReminder.minutesUntil}min ({agendaReminder.startsAt}):{" "}
        {agendaReminder.summary}
      </div>
    </div>
  );
};
