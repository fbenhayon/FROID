import React, { useState, useEffect } from "react";
interface Props { startTime?: number; onEndSession: () => void; }
export const SessionTimer: React.FC<Props> = ({ startTime, onEndSession }) => {
  const [elapsed, setElapsed] = useState(0);
  const [alertShown, setAlertShown] = useState<Record<number, boolean>>({});
  useEffect(() => {
    if (!startTime) return;
    const interval = setInterval(() => {
      const sec = Math.floor((Date.now() - startTime) / 1000);
      setElapsed(sec);
      if (sec >= 2400 && !alertShown[2400]) { setAlertShown(p => ({ ...p, 2400: true })); window.alert("⚠️ FROID: 40 minutos. Inicie encerramento gradual."); }
      if (sec >= 3000 && !alertShown[3000]) { setAlertShown(p => ({ ...p, 3000: true })); window.alert("⏰ FROID: 50 minutos. Últimos 5 minutos."); }
      if (sec >= 3300) { clearInterval(interval); window.alert("🔒 Sessão encerrada automaticamente."); onEndSession(); }
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime, alertShown, onEndSession]);
  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  return (
    <div className="w-full bg-white rounded-lg border border-slate-100 p-2 mb-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Tempo de Sessão</span>
        <span className={`text-xs font-mono font-bold ${elapsed > 3000 ? "text-red-600" : elapsed > 2400 ? "text-amber-600" : "text-slate-600"}`}>{fmt(elapsed)} / 55:00</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden"><div className={`h-full rounded-full ${elapsed > 3000 ? "bg-red-500" : elapsed > 2400 ? "bg-amber-500" : "bg-blue-500"} transition-all duration-1000`} style={{ width: `${Math.min(100, (elapsed / 3300) * 100)}%` }} /></div>
    </div>
  );
};
