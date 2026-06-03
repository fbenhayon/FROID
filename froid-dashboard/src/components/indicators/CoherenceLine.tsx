import React, { useMemo } from "react";
interface Props { status: string; }
export const CoherenceLine: React.FC<Props> = ({ status }) => {
  const meta = useMemo(() => {
    const s = (status || "NEUTRO").toUpperCase();
    if (s.includes("ALTA")) return { color: "#dc2626", pct: 95, label: "DISSONÂNCIA CRÍTICA" };
    if (s.includes("DISSONANCIA")) return { color: "#ef4444", pct: 75, label: "DISSONÂNCIA" };
    if (s.includes("EMBOTAMENTO")) return { color: "#0ea5e9", pct: 55, label: "EMBOTAMENTO" };
    if (s.includes("COERENTE")) return { color: "#22c55e", pct: 100, label: "SINCRONIA TOTAL" };
    return { color: "#94a3b8", pct: 30, label: "NEUTRO / CALIBRANDO" };
  }, [status]);
  return (
    <div className="w-full bg-white rounded-lg border border-slate-100 p-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Sincronia Voz-Face</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600`}>{meta.label}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${meta.pct}%`, backgroundColor: meta.color }} />
      </div>
    </div>
  );
};
