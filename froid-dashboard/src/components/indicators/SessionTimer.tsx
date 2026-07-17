import React, { useEffect, useRef, useState } from "react";

interface Props {
  startTime?: number;
  onEndSession: () => void;
}

export const SessionTimer: React.FC<Props> = ({ startTime, onEndSession }) => {
  const [elapsed, setElapsed] = useState(0);
  const alertShown = useRef<Record<number, boolean>>({});
  const onEndSessionRef = useRef(onEndSession);

  useEffect(() => {
    onEndSessionRef.current = onEndSession;
  }, [onEndSession]);

  useEffect(() => {
    if (!startTime) return;

    const tick = () => {
      const seconds = Math.max(0, Math.floor((Date.now() - startTime) / 1000));
      setElapsed(seconds);

      if (seconds >= 2400 && !alertShown.current[2400]) {
        alertShown.current[2400] = true;
        window.alert("FROID: 40 minutos. Inicie encerramento gradual.");
      }

      if (seconds >= 3000 && !alertShown.current[3000]) {
        alertShown.current[3000] = true;
        window.alert("FROID: 50 minutos. Últimos 5 minutos.");
      }

      if (seconds >= 3300 && !alertShown.current[3300]) {
        alertShown.current[3300] = true;
        window.alert("Sessão encerrada automaticamente.");
        onEndSessionRef.current();
      }
    };

    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [startTime]);

  const fmt = (seconds: number) =>
    `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(
      seconds % 60,
    ).padStart(2, "0")}`;

  return (
    <div className="mb-1 w-full rounded-lg border border-slate-100 bg-white p-2">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Tempo de Sessão
        </span>
        <span
          className={`font-mono text-xs font-bold ${
            elapsed > 3000
              ? "text-red-600"
              : elapsed > 2400
                ? "text-amber-600"
                : "text-slate-600"
          }`}
        >
          {fmt(elapsed)} / 55:00
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${
            elapsed > 3000
              ? "bg-red-500"
              : elapsed > 2400
                ? "bg-amber-500"
                : "bg-blue-500"
          }`}
          style={{ width: `${Math.min(100, (elapsed / 3300) * 100)}%` }}
        />
      </div>
    </div>
  );
};
